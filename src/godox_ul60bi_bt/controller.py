"""High-level controller for Godox UL60Bi Mesh Proxy commands.

Examples
--------
>>> import tempfile
>>> path = tempfile.NamedTemporaryFile(delete=True).name
>>> MeshState("00" * 16, "11" * 16, 1, 2, 10, 0).save(path)
>>> GodoxController("AA:BB", path).state.sequence_number
10
"""

from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from typing import Any

from godox_ul60bi_bt.client import ProxyClient
from godox_ul60bi_bt.crypto import (
    build_vendor_access_payload,
    k3,
    pack_proxy_config_pdu,
    pack_proxy_network_pdu,
)
from godox_ul60bi_bt.protocol import (
    build_v2_command,
    validate_brightness,
    validate_cct,
)
from godox_ul60bi_bt.state import MeshState

logger = logging.getLogger(__name__)

CONTROL_SETTLE_SECONDS = 0.25
BEACON_WAIT_TIMEOUT = 2.0
PROXY_CONFIG_ACK_TIMEOUT = 5.0


REQUEST_OPCODE = 135664


class GodoxController:
    """Control a provisioned Godox UL60Bi through Bluetooth Mesh Proxy.

    Parameters
    ----------
    address
        Platform-specific BLE address or identifier for the light.
    state_path
        Path to ``mesh_state.json`` containing the 16-byte mesh keys as hex
        strings and the current sequence number.
    client_factory
        Optional Bleak-compatible client factory for tests or custom transports.

    Examples
    --------
    >>> import tempfile
    >>> path = tempfile.NamedTemporaryFile(delete=True).name
    >>> MeshState("00" * 16, "11" * 16, 1, 2, 10, 0).save(path)
    >>> GodoxController("AA:BB", path).address
    'AA:BB'
    """

    def __init__(
        self,
        address: str,
        state_path: str | Path,
        client_factory: Any = None,
    ) -> None:
        self.address = address
        self.state_path = Path(state_path)
        self.state = MeshState.load(self.state_path)
        self._client = ProxyClient(address, client_factory=client_factory)
        self._control_write_pending = False

    async def __aenter__(self) -> GodoxController:
        """Connect and return the controller for async context manager use.

        Returns
        -------
        GodoxController
            Connected controller instance.

        Examples
        --------
        >>> GodoxController.__aenter__.__name__
        '__aenter__'
        """

        await self.connect()
        return self


    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Disconnect when leaving an async context manager.

        Parameters
        ----------
        exc_type
            Exception type raised inside the context, if any.
        exc
            Exception value raised inside the context, if any.
        tb
            Traceback raised inside the context, if any.

        Returns
        -------
        None
            The BLE proxy connection is closed.
        """

        await self.disconnect()

    async def connect(self) -> None:
        """Connect to the Mesh Proxy and install a whitelist filter.

        Returns
        -------
        None
            The proxy client connects, starts notifications, echoes the beacon
            when available, and sends proxy filter configuration PDUs.

        Examples
        --------
        >>> GodoxController.connect.__name__
        'connect'
        """

        logger.info("connecting controller to %s", self.address)
        await self._client.connect()
        logger.info("controller connected")

        beacon_event: asyncio.Event = asyncio.Event()
        proxy_ack_event: asyncio.Event = asyncio.Event()
        pending_beacon: list[bytes] = []

        def on_proxy_notify(proxy_pdu: bytes) -> None:
            pdu = bytes(proxy_pdu)
            logger.debug("raw proxy notification (%d bytes): %s", len(pdu), pdu.hex() if pdu else "<empty>")
            if not pdu:
                return
            pdu_type = pdu[0]
            if pdu_type == 0x01:
                logger.info("proxy beacon received (%d bytes): %s", len(pdu), pdu.hex())
                if len(pdu) >= 11:
                    beacon_network_id = pdu[3:11].hex()
                    our_network_id = k3(bytes.fromhex(self.state.network_key)).hex()
                    if beacon_network_id == our_network_id:
                        logger.info("beacon network ID matches our key: %s ✓", beacon_network_id)
                    else:
                        logger.warning(
                            "beacon network ID %s does not match our key (ours: %s) — wrong provisioning key!",
                            beacon_network_id,
                            our_network_id,
                        )
                pending_beacon.clear()
                pending_beacon.append(pdu)
                beacon_event.set()
            elif pdu_type == 0x02:
                logger.info(
                    "proxy config ack received (%d bytes): %s", len(pdu), pdu.hex()
                )
                proxy_ack_event.set()
            else:
                logger.info("proxy notification received (type=0x%02x): %s", pdu_type, pdu.hex())

        await self._client.start_notify(on_proxy_notify)
        logger.info("proxy notifications started")
        try:
            # Echo the Secure Network Beacon back to the device before proxy config.
            # This step is required by the Bluetooth Mesh proxy protocol: the proxy client
            # must echo the beacon to establish itself as a trusted bearer.
            try:
                await asyncio.wait_for(beacon_event.wait(), timeout=BEACON_WAIT_TIMEOUT)
                logger.info("echoing beacon back to proxy Data In")
                await self._client.write_proxy(pending_beacon[0])
            except TimeoutError:
                logger.warning("no beacon received from device; proceeding without beacon echo")

            net_key = bytes.fromhex(self.state.network_key)
            await self._send_proxy_config(
                opcode=0x00,
                parameters=bytes([0x00]),  # 0x00 = WHITELIST (0x01 = BLACKLIST, unsupported by Telink)
                net_key=net_key,
                proxy_notify=proxy_ack_event,
                label="filter type",
            )

            filter_addresses = self.state.provisioner_address.to_bytes(2, "big") + (0xFFFF).to_bytes(2, "big")
            await self._send_proxy_config(
                opcode=0x01,
                parameters=filter_addresses,
                net_key=net_key,
                proxy_notify=proxy_ack_event,
                label="whitelist",
            )
            logger.info("proxy notifications left active for session")
        finally:
            logger.info("proxy initialization complete")

    async def disconnect(self) -> None:
        """Disconnect from the Mesh Proxy.

        Returns
        -------
        None
            Notifications are stopped and the BLE connection is closed.

        Examples
        --------
        >>> GodoxController.disconnect.__name__
        'disconnect'
        """

        logger.debug("disconnecting controller for %s", self.address)
        if self._control_write_pending:
            logger.info("waiting %.2fs for control write to settle", CONTROL_SETTLE_SECONDS)
            await asyncio.sleep(CONTROL_SETTLE_SECONDS)
            self._control_write_pending = False
        await self._client.stop_notify()
        logger.info("proxy notifications stopped")
        await self._client.disconnect()

    def _advance_state(self) -> None:
        self.state = self.state.next_sequence()
        self.state.save(self.state_path)

    async def _send_proxy_config(
        self,
        *,
        opcode: int,
        parameters: bytes,
        net_key: bytes,
        proxy_notify: asyncio.Event,
        label: str,
    ) -> None:
        proxy_config = pack_proxy_config_pdu(
            opcode=opcode,
            parameters=parameters,
            net_key=net_key,
            iv_index=self.state.iv_index,
            seq=self.state.sequence_number,
            src=self.state.provisioner_address,
        )
        logger.debug("sending proxy config %s opcode=0x%02x", label, opcode)
        await self._client.write_proxy(proxy_config)
        logger.info("proxy config %s sent", label)
        self._advance_state()
        try:
            await asyncio.wait_for(proxy_notify.wait(), timeout=PROXY_CONFIG_ACK_TIMEOUT)
        except TimeoutError:
            logger.debug(
                "proxy config %s ack not received (normal — device may filter duplicate sequences)",
                label,
            )
        else:
            logger.info("proxy config %s acknowledged", label)
            proxy_notify.clear()

    async def send_v2_command(self, model: int, end_byte: int, data: bytes) -> None:
        """Send one Godox V2 vendor command through the Mesh Proxy.

        Parameters
        ----------
        model
            Godox V2 model or command family byte.
        end_byte
            V2 end byte placed before the checksum.
        data
            Exact command data bytes. V2 accepts at most five bytes; shorter
            values are padded with ``0xFF`` before transmission.

        Returns
        -------
        None
            The packed proxy PDU is written and the sequence number is advanced.

        Examples
        --------
        >>> GodoxController.send_v2_command.__name__
        'send_v2_command'
        """

        godox_payload = build_v2_command(model, end_byte, data)
        logger.info(
            "sending V2 command model=0x%02x end=0x%02x dst=0x%04x godox_payload=%s",
            model,
            end_byte,
            self.state.node_address,
            godox_payload.hex(),
        )
        access_payload = build_vendor_access_payload(REQUEST_OPCODE, godox_payload)
        net_key = bytes.fromhex(self.state.network_key)
        app_key = bytes.fromhex(self.state.app_key)
        proxy_pdu = pack_proxy_network_pdu(
            access_payload,
            net_key,
            app_key,
            iv_index=self.state.iv_index,
            seq=self.state.sequence_number,
            src=self.state.provisioner_address,
            dst=self.state.node_address,
            ttl=10,
        )

        await self._client.write_proxy(proxy_pdu)
        logger.info("vendor command sent")
        logger.debug("sent proxy PDU %s", proxy_pdu.hex())
        self._advance_state()
        self._control_write_pending = True

    async def power_on(self) -> None:
        """Send the captured Godox power-on command.

        Returns
        -------
        None
            The command is sent through :meth:`send_v2_command`.

        Examples
        --------
        >>> GodoxController.power_on.__name__
        'power_on'
        """

        logger.info("power on requested for %s", self.address)
        await self.send_v2_command(0xFE, 0xFF, bytes([0x00]))

    async def power_off(self) -> None:
        """Send the captured Godox power-off command.

        Returns
        -------
        None
            The command is sent through :meth:`send_v2_command`.

        Examples
        --------
        >>> GodoxController.power_off.__name__
        'power_off'
        """

        logger.info("power off requested for %s", self.address)
        await self.send_v2_command(0xFE, 0xFF, bytes([0x01]))

    async def set_params(
        self,
        *,
        brightness: float | None = None,
        cct: int | None = None,
    ) -> None:
        """Set brightness and color temperature in a single V2 command.

        Parameters
        ----------
        brightness
            Brightness percentage from 0 through 100. Decimal tenths are encoded
            in the V2 end byte.
        cct
            Correlated color temperature in Kelvin, from 2800 through 6500.

        Returns
        -------
        None
            A single vendor command is sent when at least one parameter is
            provided.

        Examples
        --------
        >>> GodoxController.set_params.__name__
        'set_params'
        """
        logger.info("set params requested: brightness=%s cct=%s", brightness, cct)

        # If neither is provided, do nothing
        if brightness is None and cct is None:
            return

        # Default values if one is missing (CCT 5600K, Brightness 100%)
        final_brightness = brightness if brightness is not None else 100.0
        final_cct = cct if cct is not None else 5600

        validate_brightness(int(final_brightness))
        validate_cct(final_cct)

        percent = int(final_brightness)
        brightness_point = int(round((final_brightness - percent) * 10))
        brightness_point = max(0, min(9, brightness_point))
        temp = final_cct // 100

        # Captured app traffic uses the Godox V2 0xF0 family with brightness_point in the end byte.
        # Standard CLI flow uses gm=50 and gm2=0.
        await self.send_v2_command(0xF0, brightness_point, bytes([percent, temp, 50, 0, 0]))

    async def rebind(self) -> None:
        """Re-send Config App Key Add and Model App Bind.

        Parameters
        ----------
        None
            This method uses ``device_key`` and addresses from the controller's
            mesh state.

        Returns
        -------
        None
            The command is not implemented yet and currently raises
            :class:`NotImplementedError` when a device key is present.

        Examples
        --------
        >>> GodoxController.rebind.__name__
        'rebind'
        """
        if not self.state.device_key:
            raise ValueError(
                "device_key is not set in mesh state — rebind requires the device key. "
                "Ensure your mesh_state.json contains a device_key field."
            )
        raise NotImplementedError(
            "rebind not yet implemented — run scripts/mesh_rebind2.py manually"
        )
