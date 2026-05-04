# Bluetooth Troubleshooting

## Symptoms

- `scan` sees `GD_LED`, but `inspect`, `raw`, or `replay-capture` times out while connecting.
- `scan` no longer shows `GD_LED`.
- The phone app can control the light, but the Mac cannot connect.

## Likely Causes

- The Godox Light phone app still owns the active Bluetooth session.
- The light is advertising but not accepting a second central connection.
- macOS CoreBluetooth has stale state for the fixture identifier.
- The fixture needs a Bluetooth reset or power cycle after switching between phone and Mac control.

## Recovery Flow

1. Fully close the Godox Light app on the phone.
2. Disable Bluetooth on the phone, or move the phone far enough away that it cannot reconnect.
3. Leave the light powered on.
4. Run:

   ```bash
   uv run python -m godox_ul60bi_bt scan --timeout 10
   ```

5. Confirm `GD_LED` appears.
6. Run a read-only inspection before attempting writes:

   ```bash
   uv run python -m godox_ul60bi_bt inspect 304BCD50-D2C2-4FA6-A666-F4867E54F267 --format markdown
   ```

7. If inspection still times out, power cycle the light and retry the scan/inspect sequence.
8. If macOS still times out, toggle Bluetooth off/on on the Mac and retry.

## Notes

- Seeing `GD_LED` in a scan does not prove the Mac can connect.
- A replay timeout before `write_gatt_char` does not prove replay protection or protocol failure.
- Keep phone app and Mac testing separate when validating replay behavior.
