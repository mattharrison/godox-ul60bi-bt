# Godox UL60Bi Bluetooth Tools

Python library and CLI for controlling a Godox UL60Bi Lite over Bluetooth Mesh.

The package handles the full lifecycle: provisioning a factory-reset light,
pushing the application key, and sending brightness/CCT vendor commands — all
without the Godox iOS/Android app.

The package has a working CLI for setting brightness and color temperature via
Bluetooth Mesh (Telink SDK, proxy mode). It also includes development tools for
scanning, inspecting GATT services, parsing BLE captures, and sending raw writes.

## Install

```bash
uv add godox-ul60bi-bt
```

Or for local development from this checkout:

```bash
uv sync
```

## Quick Start

### First-time setup (factory-reset light)

Provision the light (generates fresh mesh keys and saves `mesh_state.json`):

```bash
godox-ul60bi provision
```

Push the application key to the device:

```bash
godox-ul60bi rebind
```

Control the light:

```bash
godox-ul60bi set --brightness 80 --cct 4000
godox-ul60bi on
godox-ul60bi off
```

That's it. No Android app, no key extraction required.

### Subsequent sessions

After first-time setup, `mesh_state.json` persists the keys and sequence
number. Normal control commands load it automatically:

```bash
godox-ul60bi set --brightness 50 --cct 5600
```

### Migrating from the Godox app

If you have already provisioned the light with the Godox app and want to use
this library without re-provisioning, import the mesh state from a Telink
shared preferences XML (extracted from an Android debug report):

```bash
godox-ul60bi setup --import captures/telink_shared.xml
```

## Python API

Use `GodoxController` as an async context manager:

```python
import asyncio
from godox_ul60bi_bt import GodoxController


async def main() -> None:
    async with GodoxController("304BCD50-D2C2-4FA6-A666-F4867E54F267", "mesh_state.json") as light:
        await light.power_on()
        await light.set_params(brightness=80, cct=4000)


asyncio.run(main())
```

Provision programmatically:

```python
import asyncio
import dataclasses
import os
from godox_ul60bi_bt.provisioning import ProvisioningSession
from godox_ul60bi_bt.config_session import ConfigSession


async def provision_and_bind(address: str) -> None:
    net_key = os.urandom(16)
    app_key = os.urandom(16)

    # Step 1: provision (factory-reset device must be advertising)
    session = ProvisioningSession(
        address=address,
        net_key=net_key,
        key_index=0,
        iv_index=0,
        unicast_address=0x0002,
    )
    state = await session.run()
    state = dataclasses.replace(state, app_key=app_key.hex())
    state.save("mesh_state.json")

    # Step 2: push app key (device now advertising on 0x1828)
    await ConfigSession(address=address, state=state).run()


asyncio.run(provision_and_bind("304BCD50-D2C2-4FA6-A666-F4867E54F267"))
```

## Commands

```
godox-ul60bi [-v] {scan,inspect,setup,provision,rebind,on,off,set,raw}
```

### provision

Provision a factory-reset light. Scans for an unprovisioned beacon (Mesh
Provisioning Service, UUID 0x1827), runs the full BT Mesh PB-GATT provisioning
exchange, derives the device key, and saves `mesh_state.json`.

```bash
godox-ul60bi provision
godox-ul60bi provision --address 304BCD50-D2C2-4FA6-A666-F4867E54F267
godox-ul60bi provision --net-key <32-hex> --app-key <32-hex> --output my_state.json
```

Options:
- `--address`: skip scanning, connect directly
- `--net-key`: 32-hex network key (default: random)
- `--app-key`: 32-hex application key (default: random)
- `--node-addr`: unicast address to assign (default: 2)
- `--output`: where to save state (default: `./mesh_state.json`)
- `--timeout`: BLE scan timeout in seconds (default: 10)

After provisioning, run `godox-ul60bi rebind` to push the app key.

### rebind

Push Config App Key Add and Config Model App Bind to the device using the
device key. Required after every `provision` before vendor commands work.

```bash
godox-ul60bi rebind
godox-ul60bi rebind --state my_state.json
```

### set

Send a CCT/brightness vendor command:

```bash
godox-ul60bi set --brightness 80 --cct 4000
godox-ul60bi set --brightness 100 --cct 2900 --verbose
```

- `--brightness`: 0–100
- `--cct`: color temperature in Kelvin (2800–6500)
- `--seq-bump N`: advance the sequence number by N before sending (RPL recovery)

### on / off

```bash
godox-ul60bi on
godox-ul60bi off
```

### scan

Scan for provisioned Godox lights (Mesh Proxy Service, UUID 0x1828):

```bash
godox-ul60bi scan
godox-ul60bi scan --timeout 10
```

### inspect

Enumerate GATT services, characteristics, and descriptors (read-only):

```bash
godox-ul60bi inspect 304BCD50-D2C2-4FA6-A666-F4867E54F267
godox-ul60bi inspect 304BCD50-D2C2-4FA6-A666-F4867E54F267 --format markdown
```

### setup

Import or display mesh state:

```bash
godox-ul60bi setup --import mesh_state.json
godox-ul60bi setup --import captures/telink_shared.xml
godox-ul60bi setup --show
```

## State File

`mesh_state.json` holds everything needed to control the light:

```json
{
  "network_key": "98b2e7ef8211c6deca2401adbe52e715",
  "app_key": "fa0a2c615756eca3f896ce061ed4d890",
  "device_key": "6277be2be27af9818c3d79b62a2a8ae7",
  "provisioner_address": 1,
  "node_address": 2,
  "iv_index": 0,
  "sequence_number": 10
}
```

See `mesh_state.example.json` for a template with placeholder values.

The state file is loaded automatically from the first of:
1. `--state <path>` CLI flag
2. `GODOX_UL60BI_BT_STATE` environment variable
3. `./mesh_state.json`
4. `~/.config/godox-ul60bi-bt/mesh_state.json`

## How It Works

The UL60Bi Lite is a Bluetooth Mesh node, not a simple BLE peripheral. All
control commands are sent as encrypted Bluetooth Mesh Network PDUs over the
standard Mesh Proxy service (UUID 0x1828).

### Provisioning (first time)

When factory-reset, the device advertises the Mesh Provisioning Service (UUID
0x1827). The `provision` command runs the PB-GATT exchange:

1. **Invite** → device sends **Capabilities**
2. **Start** + **PublicKey** (P-256 ECDH) → device sends **PublicKey**
3. ECDH shared secret computed → **Confirmation** exchange
4. **Random** exchange → session key + device key derived
5. **Data** (encrypted network key + unicast address) → device sends **Complete**

The device key is derived from the ECDH session and is used for Config Server
messages (App Key Add, Model App Bind).

### Rebind (after every provision)

After provisioning, the device knows the network key but has no application key
bound to the vendor model. `rebind` connects over the Mesh Proxy service and
sends:

1. **Config App Key Add** — pushes the app key, encrypted with the device key
2. **Config Model App Bind** — binds the app key to the Telink vendor model

### Vendor Commands

Light control uses a Telink LE vendor model (company ID `0x0211`, model ID
`0x0000`). The access layer opcode is `0x00F011` (3 bytes, LE). The payload
encodes brightness, CCT, and a CRC-8 check byte.

## Troubleshooting

### Commands appear to have no effect (RPL rejection)

The device silently drops PDUs with a sequence number at or below its stored
high-water mark (Replay Protection List). If you used the Godox app before,
bump the sequence number:

```bash
godox-ul60bi set --seq-bump 50000 --brightness 80 --cct 4000
```

Or edit `sequence_number` in `mesh_state.json` directly.

### Proxy Filter Status acknowledgment is missing

Normal behavior. The device only sends Proxy Filter Status ACKs during the
original provisioning session. Subsequent sessions silently accept proxy config
PDUs. This is logged at DEBUG level, not WARNING.

### Need to re-provision

Factory-reset the light (hold the power button until it flashes), then:

```bash
godox-ul60bi provision
godox-ul60bi rebind
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run ty check
```

Add dependencies with `uv add` or `uv add --dev`.
