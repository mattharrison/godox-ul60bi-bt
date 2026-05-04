# Godox UL60Bi Bluetooth Tools

Python tools for controlling a Godox UL60Bi Lite over Bluetooth Mesh.

The package has a working CLI for setting brightness and color temperature via
Bluetooth Mesh (Telink SDK, proxy mode). It also includes development tools for
scanning, inspecting GATT services, parsing BLE captures, and sending raw writes.

## Install

For local development from this checkout:

```bash
uv sync
uv run python -m godox_ul60bi_bt --help
```

When published, install the package into another `uv` project with:

```bash
uv add godox-ul60bi-bt
```

## Quick Start

Scan for the light:

```bash
uv run python -m godox_ul60bi_bt scan --timeout 5
```

Import mesh state from an existing JSON file or Telink shared preferences XML:

```bash
uv run python -m godox_ul60bi_bt setup --import mesh_state.json
uv run python -m godox_ul60bi_bt setup --import captures/telink_shared.xml
```

Control the light:

```bash
uv run python -m godox_ul60bi_bt on --device <device-id>
uv run python -m godox_ul60bi_bt off --device <device-id>
uv run python -m godox_ul60bi_bt set --device <device-id> --brightness 50 --cct 5600
```

Use `--dry-run` to build and print the mesh PDU without connecting:

```bash
uv run python -m godox_ul60bi_bt set --device <device-id> --brightness 50 --cct 5600 --dry-run
```

## Python API

Use `GodoxController` when you want the library to handle Mesh Proxy setup,
packet packing, and sequence-number persistence:

```python
import asyncio

from godox_ul60bi_bt import GodoxController


async def main() -> None:
    async with GodoxController("<device-id>", "mesh_state.json") as light:
        await light.power_on()
        await light.set_params(brightness=50, cct=5600)


asyncio.run(main())
```

For lower-level work, protocol helpers are pure functions and do not require
Bluetooth hardware:

```python
from godox_ul60bi_bt.protocol import build_v2_command

payload = build_v2_command(0xF0, 0x00, bytes([50, 56, 50, 0, 0]))
print(payload.hex())
```

The low-level client classes are also available:

- `ProxyClient`: writes and receives Bluetooth Mesh Proxy PDUs through the Mesh Proxy Data In/Data Out characteristics.
- `UL60BiClient`: performs raw GATT writes and notifications for research workflows.

## Why Mesh Proxy Is Required

The UL60Bi Lite is controlled as a Bluetooth Mesh node, not as a simple BLE
peripheral with a brightness characteristic. The BLE connection exposes the
standard Bluetooth Mesh Proxy service:

- Mesh Proxy Data In: `00002add-0000-1000-8000-00805f9b34fb`
- Mesh Proxy Data Out: `00002ade-0000-1000-8000-00805f9b34fb`

High-level commands must therefore be packed as Bluetooth Mesh Network PDUs.
The proxy acts as the BLE bearer for those mesh packets. On connect, the
controller starts proxy notifications, echoes the secure network beacon when it
is available, sets a whitelist filter, and then writes encrypted vendor command
PDUs to Mesh Proxy Data In.

This is why raw captured writes are kept separate from stable SDK commands.
`raw` is useful for research, but normal control should use `on`, `off`, `set`,
or `GodoxController`, which validate inputs and pack the mesh command correctly.

## Mesh State

Bluetooth Mesh packets cannot be created from the BLE device identifier alone.
The library needs mesh state from the provisioning session:

- 16-byte Network Key, stored as 32 hex characters
- 16-byte Application Key, stored as 32 hex characters
- optional 16-byte Device Key, stored as 32 hex characters for Config messages
- source/provisioner and destination/node unicast addresses
- IV Index
- next sequence number

Already-provisioned lights cannot reveal these keys over BLE. Import state from
an existing known-good `mesh_state.json` or from Telink shared preferences
captured from the app environment.

The sequence number is security-critical: Bluetooth Mesh devices reject replayed
or older sequence numbers. This package updates `sequence_number` after every
proxy config or vendor command it sends.

When `--state` is omitted, the CLI looks for mesh state in this order:

1. `GODOX_UL60BI_BT_STATE`
2. `./mesh_state.json`
3. `~/.config/godox-ul60bi-bt/mesh_state.json`

Use `setup --import` to install state into the user config location. After
import, normal control commands do not need `--state`.

### State File Format

```json
{
  "network_key": "98b2e7ef8211c6deca2401adbe52e715",
  "app_key": "fa0a2c615756eca3f896ce061ed4d890",
  "device_key": "6277be2be27af9818c3d79b62a2a8ae7",
  "provisioner_address": 1,
  "node_address": 2,
  "iv_index": 0,
  "sequence_number": 300000
}
```

## Commands

### Logging

The CLI accepts repeatable verbosity flags:

```bash
uv run python -m godox_ul60bi_bt -v scan
uv run python -m godox_ul60bi_bt -vv inspect <device-id>
```

`-v` enables informational logs and `-vv` enables debug logs.

### Set

The `set` command sends a CCT/brightness vendor command over Bluetooth Mesh.

```bash
uv run python -m godox_ul60bi_bt set --device <device-id> --brightness 50 --cct 5600
uv run python -m godox_ul60bi_bt set --device 304BCD50-D2C2-4FA6-A666-F4867E54F267 --brightness 100 --cct 2900
uv run python -m godox_ul60bi_bt set --device <device-id> --brightness 50 --cct 5600 --dry-run
```

- `--brightness`: 0-100
- `--cct`: color temperature in Kelvin, usually 2800-6500
- `--dry-run`: print the packed PDU hex without connecting

The command reads and updates `mesh_state.json` automatically. Three sequence
numbers are consumed per call: proxy filter type, whitelist add, and vendor
command.

### Scan

```bash
uv run python -m godox_ul60bi_bt scan --timeout 5
```

The observed UL60Bi Lite advertises as `GD_LED` on this Mac. macOS reports an
opaque platform identifier rather than a stable Bluetooth MAC address.

### Inspect

```bash
uv run python -m godox_ul60bi_bt inspect <device-id> --format markdown
```

Inspection is read-only. It enumerates GATT services, characteristics,
descriptors, and properties.

### Parse Android Capture

Use Android Bluetooth HCI snoop logging with the official Godox Light app, then
convert the extracted snoop log with `tshark`:

```bash
tshark -r captures/btsnoop_hci.log -Y "btatt.opcode == 0x12 || btatt.opcode == 0x52" -T json > captures/godox-att-writes.json
uv run python -m godox_ul60bi_bt parse-capture captures/godox-att-writes.json --format markdown
```

See [captures/README.md](captures/README.md) for the full Android capture
workflow.

### Raw Writes

Raw writes are for confirmed packets captured from the official app.

```bash
uv run python -m godox_ul60bi_bt raw --device <device-id> --char <uuid> --hex <payload-hex>
```

Use this only after the characteristic and bytes are confirmed from captured app
traffic.

## Troubleshooting

### Commands appear to have no effect

The most likely cause is Replay Protection List (RPL) rejection.

The device maintains a per-source high-water mark for sequence numbers. Any
incoming mesh PDU with a sequence number at or below the stored high-water mark
is silently dropped. There is no error and no acknowledgment.

This happens whenever:

- The Godox Light Android/iOS app was used before your Python session.
- `mesh_state.json` has a `sequence_number` that is too low.

Fix this by bumping `sequence_number` in `mesh_state.json` well above the last
value used by the app. Setting it to `300000` or higher is safe for current
captures.

```json
{ "sequence_number": 300000 }
```

After using the Godox app again, bump `sequence_number` again before the next
Python control call.

### Proxy Filter Status acknowledgment is missing

This is normal for standalone reconnect sessions. The device only sends Proxy
Filter Status during the same BLE session as provisioning. In subsequent
sessions it silently accepts the proxy config PDUs, unless RPL rejects them.

## Development

This project uses `uv`.

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

Dependencies should be added with `uv add` or `uv add --dev`; do not edit
dependency entries in `pyproject.toml` directly.

## Hardware Workflows

- [Bluetooth troubleshooting](docs/troubleshooting.md)
- [Hardware smoke tests](docs/hardware-tests.md)
