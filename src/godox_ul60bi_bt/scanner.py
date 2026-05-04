"""Discover Godox BLE devices.

Examples
--------
>>> device = DiscoveredDevice("GD_LED", "AA:BB", -60, Advertisement(), False)
>>> is_likely_godox_device(device)
True
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from bleak import BleakScanner

logger = logging.getLogger(__name__)


DiscoverFn = Callable[
    ...,
    Awaitable[dict[str, tuple[Any, Any]]],
]


@dataclass(frozen=True)
class Advertisement:
    """Bluetooth advertisement details captured during scanning.

    Parameters
    ----------
    local_name
        Local name from the advertisement payload, if present.
    service_uuids
        Advertised service UUID strings.
    manufacturer_data
        Manufacturer data keyed by company identifier, with each byte payload
        preserved as a hexadecimal string.

    Examples
    --------
    >>> Advertisement(local_name="GD_LED", manufacturer_data={1: "aabb"}).to_dict()
    {'local_name': 'GD_LED', 'service_uuids': [], 'manufacturer_data': {'1': 'aabb'}}
    """

    local_name: str | None = None
    service_uuids: tuple[str, ...] = ()
    manufacturer_data: dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert advertisement data to JSON-serializable values.

        Returns
        -------
        dict[str, object]
            Advertisement data with manufacturer byte payloads as hex strings.

        Examples
        --------
        >>> Advertisement(service_uuids=("180f",)).to_dict()["service_uuids"]
        ['180f']
        """

        return {
            "local_name": self.local_name,
            "service_uuids": list(self.service_uuids),
            "manufacturer_data": {
                str(company_id): payload
                for company_id, payload in sorted(self.manufacturer_data.items())
            },
        }


@dataclass(frozen=True)
class DiscoveredDevice:
    """A BLE device discovered during a scan.

    Parameters
    ----------
    name
        Device name reported by the platform or advertisement.
    address
        Platform-specific BLE address or identifier.
    rssi
        Received signal strength in dBm, if provided by the platform.
    advertisement
        Parsed advertisement details.
    likely_godox
        Whether the name matches known Godox UL60Bi advertising patterns.

    Examples
    --------
    >>> DiscoveredDevice("GD_LED", "AA:BB", -60, Advertisement(), True).to_dict()["likely_godox"]
    True
    """

    name: str | None
    address: str
    rssi: int | None
    advertisement: Advertisement
    likely_godox: bool

    def to_dict(self) -> dict[str, object]:
        """Convert the discovered device to JSON-serializable values.

        Returns
        -------
        dict[str, object]
            Device fields and nested advertisement data.

        Examples
        --------
        >>> DiscoveredDevice(None, "AA:BB", None, Advertisement(), False).to_dict()["address"]
        'AA:BB'
        """

        return {
            "name": self.name,
            "address": self.address,
            "rssi": self.rssi,
            "likely_godox": self.likely_godox,
            "advertisement": self.advertisement.to_dict(),
        }


def is_likely_godox_device(device: DiscoveredDevice) -> bool:
    """Return whether a discovered device looks like a Godox light.

    Parameters
    ----------
    device
        Device returned by :func:`scan`.

    Returns
    -------
    bool
        ``True`` when the device or advertisement name matches known Godox
        names.

    Examples
    --------
    >>> is_likely_godox_device(DiscoveredDevice("GD_LED", "AA:BB", None, Advertisement(), False))
    True
    """

    names = [
        device.name,
        device.advertisement.local_name,
    ]
    return any(_looks_like_godox_name(name) for name in names)


async def scan(
    *,
    timeout: float = 5.0,
    discover: DiscoverFn | None = None,
) -> list[DiscoveredDevice]:
    """Scan for BLE devices and mark likely Godox lights.

    Parameters
    ----------
    timeout
        Scan duration in seconds.
    discover
        Optional Bleak-compatible discovery coroutine for tests.

    Returns
    -------
    list[DiscoveredDevice]
        Devices sorted with likely Godox devices first.

    Examples
    --------
    >>> import asyncio
    >>> class Device:
    ...     name = "GD_LED"
    ...     address = "AA:BB"
    >>> class Adv:
    ...     local_name = None
    ...     service_uuids = ()
    ...     manufacturer_data = {}
    ...     rssi = -60
    >>> async def fake_discover(**kwargs):
    ...     return {"AA:BB": (Device(), Adv())}
    >>> asyncio.run(scan(discover=fake_discover))[0].likely_godox
    True
    """

    discover_fn = discover or BleakScanner.discover
    logger.debug("starting scan with timeout=%s", timeout)
    raw_devices = await discover_fn(timeout=timeout, return_adv=True)

    devices = [
        _build_discovered_device(ble_device, advertisement_data)
        for ble_device, advertisement_data in raw_devices.values()
    ]
    logger.info("scan discovered %d device(s)", len(devices))
    return sorted(devices, key=lambda device: (not device.likely_godox, device.name or "", device.address))


def _build_discovered_device(
    ble_device: Any,
    advertisement_data: Any,
) -> DiscoveredDevice:
    local_name = _get_attr(advertisement_data, "local_name")
    device_name = ble_device.name or local_name
    advertisement = Advertisement(
        local_name=local_name,
        service_uuids=tuple(_get_attr(advertisement_data, "service_uuids") or ()),
        manufacturer_data=_manufacturer_data_as_hex(
            _get_attr(advertisement_data, "manufacturer_data") or {}
        ),
    )
    device = DiscoveredDevice(
        name=device_name,
        address=ble_device.address,
        rssi=_get_attr(advertisement_data, "rssi"),
        advertisement=advertisement,
        likely_godox=False,
    )
    return DiscoveredDevice(
        name=device.name,
        address=device.address,
        rssi=device.rssi,
        advertisement=device.advertisement,
        likely_godox=is_likely_godox_device(device),
    )


def _looks_like_godox_name(name: str | None) -> bool:
    if not name:
        return False
    normalized = name.lower().replace(" ", "").replace("-", "")
    return normalized in {"gd_led"} or "godox" in normalized or "ul60bi" in normalized


def _manufacturer_data_as_hex(manufacturer_data: dict[int, bytes]) -> dict[int, str]:
    return {
        company_id: bytes(payload).hex()
        for company_id, payload in sorted(manufacturer_data.items())
    }


def _get_attr(value: Any, name: str) -> Any:
    return getattr(value, name, None)
