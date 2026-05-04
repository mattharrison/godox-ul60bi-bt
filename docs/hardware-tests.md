# Hardware Smoke Tests

Hardware tests require the Godox UL60Bi Lite to be powered on and visible over Bluetooth.

## Opt In

Hardware tests are skipped by default. Enable them explicitly:

```bash
GODOX_UL60BI_BT_HARDWARE=1 uv run pytest -m hardware
```

## Manual Smoke Procedure

1. Close the Godox Light app on the phone.
2. Make sure the phone is not connected to the light.
3. Power on the light.
4. Run a scan:

   ```bash
   uv run python -m godox_ul60bi_bt scan --timeout 10
   ```

5. Confirm `GD_LED` appears and record the macOS identifier.
6. Run read-only inspection:

   ```bash
   uv run python -m godox_ul60bi_bt inspect <device-id> --format markdown
   ```

7. Save any scan, inspection, or replay results in `captures/`.

## Control Dry Run Procedure

Run a dry run before every live control attempt. This does not connect to the light and does not advance the mesh sequence.

```bash
uv run python -m godox_ul60bi_bt set \
  --device <device-id> \
  --state mesh_state.json \
  --node-address 0x0002 \
  --brightness 95 \
  --dry-run
```

Record the JSON output in the live-test notes. Confirm these fields before sending a real command:

- `ble_device` matches the macOS Bluetooth identifier from `scan`.
- `mesh_dst` is `0x0002`.
- `vendor_opcode` is `135664`.
- `godox_v2_payload_hex` starts with `f05f3832000000` for `brightness 95`.
- `proxy_pdu_hex` is present.

## Live Control Observation Procedure

Only run a live control command after the dry-run output matches expectations.

```bash
uv run python -m godox_ul60bi_bt -vv set \
  --device <device-id> \
  --state mesh_state.json \
  --node-address 0x0002 \
  --brightness 95
```

Record all of the following:

- Exact command.
- Dry-run JSON.
- Verbose log line containing `dst=0x0002`.
- Verbose log line containing `godox_payload=f05f3832000000`.
- Whether the BLE write completed.
- Fixture display brightness before the command.
- Fixture display brightness after the command.
- Whether the physical light output changed.

Do not treat a BLE write as successful control unless the fixture display or light output changes in the expected direction.

## Replay Smoke Procedure

Replay writes are live control attempts. Use only captured official-app packets.

1. Confirm the device is visible with `scan`.
2. Confirm the device can connect with `inspect`.
3. Run one low-risk captured replay packet.
4. Record:
   - command
   - capture file
   - row number
   - characteristic UUID
   - whether the write completed
   - observed physical result

Do not mark replay tasks complete unless the write reaches the fixture and the physical result is recorded.
