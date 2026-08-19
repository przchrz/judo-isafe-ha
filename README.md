# JUDO ZEWA i-SAFE — Home Assistant integration

Local, poll-based integration for the JUDO **ZEWA i-SAFE** leakage protection device
(device type `0x44`) via the REST API of the JUDO connectivity module.

> Unofficial and unaffiliated with JUDO Wasseraufbereitung GmbH. Built from the
> publicly published command list. Use at your own risk — this device controls
> your main water supply.

## Installation

Copy `custom_components/judo_isafe/` into your Home Assistant `config/custom_components/`
directory and restart, then add **JUDO ZEWA i-SAFE** from *Settings → Devices & services*.

Defaults for the connectivity module are host port `80`, user `admin`, password `Connectivity`.

## What you get

Firmware varies significantly across i-SAFE units, so the integration **probes** the
optional read commands at setup instead of trusting the device type. Entities that
depend on an unsupported command are simply not created.

| Platform | Entities | Requires |
|---|---|---|
| `valve` | Leakage protection valve with real open/closed/moving state | status read (`69`) |
| `binary_sensor` | Water flowing; leakage; flow/volume/duration limits; microleak; learn mode; 7 diagnostic bits | status read (`69`) except *Water flowing* |
| `sensor` | Total water, water flow, leak cause, learn-mode remaining water, operating days, device time | — |
| `button` | Sleep/holiday start+end, microleak test, learn mode, reset message, and valve open/close when there is no status read | — |
| `number` | Absence limits, leakage limits, sleep duration | partially |
| `select` | Microleak test mode, holiday profile, priority | — |

Absence time windows and the learn-mode accept/discard decision are **services**
(`judo_isafe.set_absence_window`, `clear_absence_window`, `acknowledge_learn_mode`),
because they are multi-field records and one-shot decisions rather than states.

## Water flow is derived, not measured

The i-SAFE compares flow against its configured limits internally but **never reports
the value**. The only usable signal is the cumulative litre counter (command `28`), so
flow is obtained by differentiating it over a configurable window.

Because the counter has 1-litre granularity, sensitivity trades directly against latency:

| Averaging window | Smallest detectable rate |
|---|---|
| 30 s | ~120 l/h |
| 2 min (default) | ~30 l/h |
| 10 min | ~6 l/h |

A shower (~500 l/h) registers almost immediately; a dripping tap will not. Use the
device's own microleak detection for that.

## Firmware differences

Several shipping units reject commands that the manual documents:

| Command | Effect when unsupported |
|---|---|
| `69` status word | No valve entity and no status binary sensors; valve control degrades to buttons |
| `68` leakage settings read | Max flow/volume/duration become write-only and restore their last value from Home Assistant |
| `66` sleep duration read | Sleep duration becomes write-only |

Check yours before assuming anything:

```bash
curl -u admin:Connectivity http://<device-ip>/api/rest/6900
curl -u admin:Connectivity http://<device-ip>/api/rest/6800
```

> **Never sweep unknown command IDs.** They are reused across JUDO device families:
> `5100` reads the target water hardness on an i-soft softener but **closes the main
> water valve** on the i-SAFE. The integration only ever probes documented reads.

## Protocol notes

- Request format is `GET /api/rest/<CMD>00<payload-hex>`, response is JSON with a hex `data` field.
- Multi-byte values are **little-endian**, verified against the manual's own examples.
- The manual's `5F` (absence limits write) example is internally inconsistent: it annotates
  `9C04` as 2500 l/h, but that decodes to 1180; 2500 encodes as `C409`. The annotation is
  wrong, not the byte order — see `tests/test_models.py`.
- Command `0E` (commissioning date) does not decode cleanly as little-endian and is not exposed.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest ruff
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

`models.py` and `flow_tracker.py` are free of Home Assistant imports, so the wire format
and the flow derivation are unit tested without a Home Assistant install. Test vectors are
taken directly from the published command list.
