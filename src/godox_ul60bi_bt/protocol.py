"""Build and parse Godox vendor payloads.

Examples
--------
>>> build_v2_command(0xFE, 0xFF, bytes([0x00])).hex()
'fe00ffffffffff7f'
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from godox_ul60bi_bt.crypto import checksum

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class BatteryPower:
    """Parsed battery and power status fields.

    Parameters
    ----------
    state
        Raw power-state byte reported by the light.
    hour
        Remaining runtime hours reported by the light.
    minute
        Remaining runtime minutes reported by the light.
    option
        Battery option bit extracted from the response.
    power_percent
        Battery power percentage.

    Examples
    --------
    >>> parse_battery_power_response(bytes.fromhex("a600000040000000")).power_percent
    64
    """

    state: int
    hour: int
    minute: int
    option: int
    power_percent: int


@dataclass(frozen=True)
class GodoxV2Payload:
    """Decoded fixed-width Godox V2 command payload.

    Parameters
    ----------
    model
        Godox model or command family byte.
    data
        Five command data bytes.
    end_byte
        Command terminator or brightness decimal byte.
    checksum
        CRC-8 checksum byte.

    Examples
    --------
    >>> parse_v2_payload(bytes.fromhex("fe00ffffffffff7f")).model
    254
    """

    model: int
    data: bytes
    end_byte: int
    checksum: int


def validate_brightness(value: int) -> int:
    """Validate a Godox brightness percentage.

    Parameters
    ----------
    value
        Brightness percentage from 0 through 100.

    Returns
    -------
    int
        The validated brightness value.

    Examples
    --------
    >>> validate_brightness(50)
    50
    >>> validate_brightness(101)
    Traceback (most recent call last):
    ...
    ValueError: brightness must be between 0 and 100
    """

    if not 0 <= value <= 100:
        raise ValueError("brightness must be between 0 and 100")
    return value


def validate_cct(value: int) -> int:
    """Validate a Godox correlated color temperature value.

    Parameters
    ----------
    value
        Color temperature in Kelvin.

    Returns
    -------
    int
        The validated color temperature.

    Examples
    --------
    >>> validate_cct(5600)
    5600
    >>> validate_cct(2700)
    Traceback (most recent call last):
    ...
    ValueError: CCT must be between 2800K and 6500K
    """

    if not 2800 <= value <= 6500:
        raise ValueError("CCT must be between 2800K and 6500K")
    return value


def build_v2_command(model: int, end_byte: int, data: bytes) -> bytes:
    """Build an 8-byte Godox V2 command payload.

    Parameters
    ----------
    model
        Godox model or command family byte.
    end_byte
        End byte to place before the checksum.
    data
        Up to five command data bytes; shorter values are padded with ``0xFF``.

    Returns
    -------
    bytes
        Packed V2 payload as ``model + padded data + end_byte + checksum``.

    Examples
    --------
    >>> build_v2_command(0xFE, 0xFF, bytes([0x00])).hex()
    'fe00ffffffffff7f'
    """
    if len(data) > 5:
        raise ValueError("V2 command data must be at most 5 bytes")

    # Pad data with 0xFF up to 5 bytes
    padded_data = data + b"\xFF" * (5 - len(data))
    payload = bytes([model]) + padded_data + bytes([end_byte])
    crc = checksum(payload)
    command = payload + bytes([crc])
    logger.debug("built V2 command model=0x%02x len=%d", model, len(command))
    return command


def parse_v2_payload(payload: bytes) -> GodoxV2Payload:
    """Parse and validate an 8-byte Godox V2 command payload.

    Parameters
    ----------
    payload
        Full V2 payload including checksum.

    Returns
    -------
    GodoxV2Payload
        Parsed payload fields.

    Examples
    --------
    >>> parsed = parse_v2_payload(bytes.fromhex("f032383200000032"))
    >>> parsed.data.hex()
    '3238320000'
    """

    if len(payload) != 8:
        raise ValueError("V2 payload must be exactly 8 bytes")

    expected = checksum(payload[:7])
    actual = payload[7]
    if actual != expected:
        raise ValueError("invalid V2 payload checksum")

    parsed = GodoxV2Payload(
        model=payload[0],
        data=payload[1:6],
        end_byte=payload[6],
        checksum=actual,
    )
    logger.debug("parsed V2 payload model=0x%02x", parsed.model)
    return parsed


def build_v3_command(cmd: int, data: bytes) -> bytes:
    """Build a variable-length Godox V3 command payload.

    Parameters
    ----------
    cmd
        V3 command byte.
    data
        Command data bytes.

    Returns
    -------
    bytes
        Packed V3 payload with length and checksum bytes.

    Examples
    --------
    >>> build_v3_command(0xA6, b"\\x01").hex()
    'a6040142'
    """
    length = len(data) + 3
    payload = bytes([cmd, length]) + data
    crc = checksum(payload)
    command = payload + bytes([crc])
    logger.debug("built V3 command cmd=0x%02x len=%d", cmd, len(command))
    return command


def parse_battery_power_response(data: bytes) -> BatteryPower:
    """Parse a Godox V3 battery/power response.

    Parameters
    ----------
    data
        Raw response bytes beginning with ``0xA6``.

    Returns
    -------
    BatteryPower
        Parsed power status.

    Examples
    --------
    >>> parse_battery_power_response(bytes.fromhex("a600000040000000"))
    BatteryPower(state=0, hour=0, minute=0, option=0, power_percent=64)
    """

    if len(data) < 8:
        raise ValueError("battery response must be at least 8 bytes")
    if data[0] != 0xA6:
        raise ValueError("battery response must start with 0xA6")

    parsed = BatteryPower(
        state=data[1],
        hour=data[2],
        minute=data[3],
        option=data[4] >> 7,
        power_percent=data[4] & 0x7F,
    )
    logger.debug("parsed battery response percent=%d", parsed.power_percent)
    return parsed


