# Creta Longitudinal Control Strategy

This note is about getting openpilot longitudinal control working on the working `creta-v11` branch.

Current known-good baseline:

```text
openpilot branch: creta-v11
opendbc branch:   creta-dbc-v11
platform:         HYUNDAI_CRETA_2ND_GEN
```

The car installs, boots, and is recognized. It is recognized even without an EPS firmware fingerprint.

## What Has To Be True

For Hyundai/Kia/Genesis, openpilot longitudinal control is gated by platform eligibility and by a user/developer toggle. The official supported-cars docs describe openpilot Longitudinal Control as an Alpha feature that is behind a toggle on non-release branches.

Relevant local code:

```text
opendbc_repo/opendbc/car/hyundai/interface.py
selfdrive/ui/layouts/settings/developer.py
selfdrive/selfdrived/selfdrived.py
```

For non-CAN-FD Hyundai cars, this branch does:

```python
ret.alphaLongitudinalAvailable = candidate not in UNSUPPORTED_LONGITUDINAL_CAR
ret.openpilotLongitudinalControl = alpha_long and ret.alphaLongitudinalAvailable
ret.pcmCruise = not ret.openpilotLongitudinalControl
```

So for the Creta, the first checks are:

```bash
cd /data/openpilot
python - <<'PY'
from cereal import messaging, car
from openpilot.common.params import Params

cp = messaging.log_from_bytes(Params().get("CarParamsPersistent"), car.CarParams)
print("carFingerprint:", cp.carFingerprint)
print("alphaLongitudinalAvailable:", cp.alphaLongitudinalAvailable)
print("openpilotLongitudinalControl:", cp.openpilotLongitudinalControl)
print("pcmCruise:", cp.pcmCruise)
print("flags:", cp.flags)
for cfg in cp.safetyConfigs:
  print("safety:", cfg.safetyModel, cfg.safetyParam)
PY
```

Expected first milestone:

```text
alphaLongitudinalAvailable: True
```

Expected second milestone after enabling the toggle and cycling offroad/onroad:

```text
openpilotLongitudinalControl: True
pcmCruise: False
```

If `alphaLongitudinalAvailable` is false, the platform is being treated as unsupported for long. If `alphaLongitudinalAvailable` is true but `openpilotLongitudinalControl` is false, the toggle is not enabled or was removed by release/availability gating.

## Best Bet

Best bet: treat this as a standard non-CAN-FD Hyundai SCC car first, and verify whether it behaves like the existing non-camera-SCC platforms.

That means:

1. Leave `HYUNDAI_CRETA_2ND_GEN` without `CAMERA_SCC`, `RADAR_SCC`, `LEGACY`, or `UNSUPPORTED_LONGITUDINAL` flags for the first long-control test.
2. Enable the longitudinal alpha toggle offroad.
3. Confirm `CarParamsPersistent` has `openpilotLongitudinalControl=True`.
4. Test carefully at low speed with the stock SCC radar disabled by openpilot.
5. Watch for SCC/FCA faults, cruise unavailable, AEB warnings, or missing acceleration response.

Why this is the best first test:

- The Creta is currently recognized with the generic Hyundai DBC path.
- The platform is not in the local unsupported-longitudinal set.
- The current Hyundai interface already knows how to set `HyundaiSafetyFlags.LONG` and disable the SCC radar for non-camera-SCC openpilot long.
- This tests the smallest possible change in behavior: enabling long without changing platform flags first.

## Likely Failure Modes

### 1. Alpha Toggle Is Not Actually Enabled

The UI hides the alpha long toggle on release builds and removes `AlphaLongitudinalEnabled` if the platform is not alpha-long available.

Local code:

```text
selfdrive/ui/layouts/settings/developer.py
selfdrive/selfdrived/selfdrived.py
```

Symptoms:

```text
alphaLongitudinalAvailable=True
openpilotLongitudinalControl=False
pcmCruise=True
```

Action:

- Confirm this custom branch is treated as non-release.
- Enable the alpha long toggle offroad.
- Power cycle or cycle offroad/onroad so CarParams are regenerated.

### 2. Creta Is Camera-SCC, Not Radar-SCC

Some Hyundai platforms use camera-based SCC rather than radar-based SCC. In this codebase, that changes safety flags, button bus, AEB/FCA forwarding, and whether openpilot tries to disable the radar ECU.

Relevant local flags:

```text
HyundaiFlags.CAMERA_SCC
HyundaiSafetyFlags.CAMERA_SCC
```

Relevant local behavior:

```python
if CP.openpilotLongitudinalControl and not (CP.flags & (HyundaiFlags.CANFD_CAMERA_SCC | HyundaiFlags.CAMERA_SCC)):
  disable_ecu(... addr=0x7d0 ...)
```

Symptoms if we get this wrong:

- Cruise unavailable.
- SCC fault on dash.
- AEB/FCA fault.
- openpilot sends ACC messages but the car ignores them.
- Radar disable attempt fails or disables the wrong thing.

Action:

- Check whether SCC messages originate from camera bus or powertrain bus.
- Compare live CAN bus presence for SCC11/SCC12/SCC13/SCC14/FCA11/FCA12 before enabling long.
- If stock SCC is camera-based, test `HyundaiFlags.CAMERA_SCC`.

### 3. CRC8 Memory: Probably LKAS, Not The Main Long-Control Gate

The memory about CRC8 may be real, but in this branch `HyundaiFlags.CHECKSUM_CRC8` affects the `LKAS11` steering checksum path:

```text
opendbc_repo/opendbc/car/hyundai/hyundaican.py
```

Local code:

```python
if CP.flags & HyundaiFlags.CHECKSUM_CRC8:
  checksum = hyundai_checksum(dat_without_checksum)
elif CP.flags & HyundaiFlags.CHECKSUM_6B:
  checksum = sum(dat[:6]) % 256
else:
  checksum = (sum(dat[:6]) + dat[7]) % 256
```

The long-control ACC messages use their own SCC/FCA helpers:

```text
SCC11
SCC12
SCC13
SCC14
FCA11
FCA12
FRT_RADAR11
```

So CRC8 is more likely to explain a steering/LKAS checksum behavior than a pure longitudinal failure. However, many newer non-CAN-FD Hyundai SCC platforms with known long support also carry `CHECKSUM_CRC8`, so it may correlate with the platform generation that worked before.

Action:

- If lateral works cleanly with no LKAS faults, do not make CRC8 the first long-control change.
- If there are LKAS checksum faults or steering messages are rejected, compare Creta LKAS11 checksum with stock and test `HyundaiFlags.CHECKSUM_CRC8`.
- Do not add `CHECKSUM_CRC8` just because long fails; first determine whether SCC/FCA messages are the failure point.

### 4. Missing FCA / AEB Behavior

The local Hyundai interface sets `USE_FCA` dynamically if message `0x38d` is seen:

```python
if 0x38d in fingerprint[0] or 0x38d in fingerprint[2]:
  ret.flags |= HyundaiFlags.USE_FCA.value
```

If the Creta has an FCA variant with different checksum/counter expectations, long may fault when openpilot starts sending or suppressing ACC/AEB-related messages.

Symptoms:

- AEB disabled warning.
- FCA warning.
- TCS fault.
- Long works briefly then faults.

Action:

- Capture whether `0x38d` exists and which bus it is on.
- Compare stock FCA11/FCA12 counter/checksum behavior.
- Confirm whether `create_acc_commands()` should use FCA for this platform.

### 5. SCC Radar Disable Fails

For non-camera-SCC openpilot long, this branch attempts to silence the SCC radar ECU at address `0x7d0`.

Symptoms:

- Long toggle enabled, but stock SCC still sends conflicting messages.
- Control mismatch.
- Cruise unavailable.
- Car alternates between stock and openpilot ACC behavior.

Action:

- Check logs around `disable_ecu`.
- Watch whether SCC11/SCC12 stock messages stop after init.
- If stock SCC is not disabled, investigate whether bus/address differs or whether Creta needs camera-SCC behavior.

### 6. Missing Radar Tracks Or Radar DBC Path

The Creta platform currently uses the generic Hyundai DBC map unless flags change. `ret.radarUnavailable` is computed from radar message presence and whether the platform DBC map has a radar bus entry.

For openpilot long, radar tracks may not be strictly required, but they can matter for lead behavior and stopped-car behavior.

Action:

- Check `CarParamsPersistent.radarUnavailable`.
- Check whether bus 1 has radar points around `RADAR_START_ADDR`.
- If radar points exist, consider whether the platform should use `HyundaiFlags.MANDO_RADAR`.

## Suggested Test Order

1. Confirm current CarParams with stock longitudinal:

```bash
cd /data/openpilot
python - <<'PY'
from cereal import messaging, car
from openpilot.common.params import Params
cp = messaging.log_from_bytes(Params().get("CarParamsPersistent"), car.CarParams)
for name in ("carFingerprint", "alphaLongitudinalAvailable", "openpilotLongitudinalControl", "pcmCruise", "radarUnavailable", "flags"):
  print(name, getattr(cp, name))
for cfg in cp.safetyConfigs:
  print("safety", cfg.safetyModel, cfg.safetyParam)
PY
```

2. Enable alpha long offroad and regenerate CarParams.

3. Confirm:

```text
openpilotLongitudinalControl=True
safetyParam includes LONG
pcmCruise=False
```

4. If the car faults immediately, first classify the fault:

```text
toggle unavailable -> availability/release gating
cruise unavailable -> SCC mode, radar disable, or SCC message mismatch
AEB/FCA warning -> USE_FCA/FCA checksum/counter path
LKAS/steering fault -> CHECKSUM_CRC8 or LKAS11 behavior
```

5. Only then test one flag at a time:

```text
CAMERA_SCC
CHECKSUM_CRC8
MANDO_RADAR
USE_FCA behavior
UNSUPPORTED_LONGITUDINAL only if we need to temporarily protect the branch
```

## Sources

- openpilot docs: supported cars footnote says openpilot Longitudinal Control is Alpha and is behind a toggle on non-release branches: https://docs.comma.ai/CARS/
- comma.ai openpilot overview says openpilot uses the car's existing APIs and performs ACC/ALC where supported: https://www.comma.ai/openpilot
- sunnypilot community explanation, useful as cross-fork context, says Hyundai/Kia/Genesis alpha long generally applies to most SCC-equipped models not in an unsupported longitudinal list and is disabled for non-SCC vehicles: https://community.sunnypilot.ai/t/alpha-longitudinal/1329
- Hyundai/Kia/Genesis wiki summary describes SCC as the ACC system and notes that, in many HKG cases, stock SCC provides longitudinal unless openpilot long is enabled: https://github-wiki-see.page/m/commaai/openpilot/wiki/Hyundai-Kia-Genesis
