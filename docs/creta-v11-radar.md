# Creta v11 Radar Information Inventory

This note documents radar-adjacent data that may be available on the Hyundai Creta 2024 v11 branch, before choosing what to surface on the HUD.

## Vehicle/branch facts

- Branch base: `creta-v11` (`b6752d9d1`).
- Platform: `CAR.HYUNDAI_CRETA_2ND_GEN`.
- DBC in current platform config: `hyundai_kia_generic` on `Bus.pt`.
- Current platform flags: no `MANDO_RADAR`, no `CAMERA_SCC`, no `RADAR_SCC`, no CAN-FD flags.
- Known firmware entries:
  - Forward camera: `SU2BMFC AT BRA LHD ... 99211-BX000`.
  - Forward radar: `SU2b FCA F-CUP ... 99110-BX000`.

Interpretation: the car appears to have a forward radar/FCA module, but the current platform config does not enable openpilot's raw Mando radar track parser. Today, the easiest known radar-related data path is through stock SCC/FCA summary/status messages in `hyundai_kia_generic`.

## Current openpilot parser behavior

For non-CAN-FD Hyundai, `CarState` chooses the cruise data source as:

- `cp` on powertrain bus by default.
- `cp_cam` only if `HyundaiFlags.CAMERA_SCC` is set.

Creta does not set `CAMERA_SCC`, so current code reads SCC/FCA from powertrain bus.

Fields already consumed:

- `SCC11.MainMode_ACC`: stock ACC availability.
- `SCC12.ACCMode`: stock ACC enabled/override/off state.
- `SCC11.SCCInfoDisplay`: standstill/non-adaptive dashboard state.
- `SCC11.VSetDis`: stock cruise set speed.
- `SCC12.TakeOverReq`: used as possible stock FCW.
- `SCC12` or `FCA11` warning/braking bits: used for `stockFcw` and `stockAeb`.

Radar availability in `CarParams` is currently:

- `ret.radarUnavailable = RADAR_START_ADDR not in fingerprint[1] or Bus.radar not in DBC[carFingerprint]`
- `RADAR_START_ADDR = 0x500`
- Because Creta has no `MANDO_RADAR` flag, `Bus.radar` is not in its DBC map, so raw radar is considered unavailable even if a physical module is present.

## Stock SCC summary object data

Message: `SCC11` (`0x420`, 1056 decimal), source `SCC`.

Potentially HUD-relevant fields:

- `ObjValid`: boolean-ish lead/object validity.
- `ACC_ObjStatus`: object status, range `0..3`.
- `ACC_ObjDist`: object distance, scale `0.1 m`, range `0..204.7 m`.
- `ACC_ObjRelSpd`: relative speed, scale `0.1 m/s`, offset `-170`.
- `ACC_ObjLatPos`: lateral position, scale `0.1 m`, offset `-20`.
- `TauGapSet`: selected following gap, range `0..7`.
- `SCCInfoDisplay`: dashboard status. Known values in DBC:
  - `0`: No Message
  - `2`: Cruise Control
  - `3`: Lost Lead
  - `4`: Standstill
- `VSetDis`: stock set speed in km/h or mph.

Possible HUD uses:

- Small lead chip: `lead: valid/none`.
- Lead distance: `ACC_ObjDist`.
- Relative speed: `ACC_ObjRelSpd`.
- Lost-lead or standstill hints from `SCCInfoDisplay`.
- Selected following gap from `TauGapSet`.

Risk/unknowns:

- `ObjValid`/`ACC_ObjStatus` semantics need live validation on Creta.
- `ACC_ObjRelSpd` has a broad DBC range and may use sentinel values.
- If stock SCC is off or unavailable, this message may continue with stale/neutral fields.

## Stock SCC control/status data

Message: `SCC12` (`0x421`, 1057 decimal), source `SCC`.

Potentially HUD-relevant fields:

- `ACCMode`: stock ACC state. Known values:
  - `0`: off
  - `1`: enabled
  - `2`: driver_override
  - `3`: off_maybe_fault
- `ACCFailInfo`: fault/fail info.
- `TakeOverReq`: takeover request/FCW-like prompt.
- `AEB_Status`, `AEB_CmdAct`, `AEB_StopReq`, `AEB_Failinfo`: AEB state.
- `CF_VSM_Warn`: warning state.
- `CR_VSM_DecCmd`: requested decel in g.
- `aReqRaw`, `aReqValue`: acceleration request in `m/s^2`.

Possible HUD uses:

- Debug status for stock SCC: off/enabled/override/fault.
- AEB/FCW indicators for validating what stock system sees.
- Takeover request indication.

Risk/unknowns:

- These are more status/control than object data.
- They are useful as debug overlays, but probably too noisy for the main HUD.

## Stock SCC comfort/gap display data

Message: `SCC14` (`0x389`, 905 decimal), source `SCC`.

Potentially HUD-relevant fields:

- `ACCMode`: ACC state for CLU/HUD.
- `ObjGap`: object gap for CLU/HUD. Existing transmit-side comment says:
  - `5`: >30 m
  - `4`: 25-30 m
  - `3`: 20-25 m
  - `2`: <20 m
  - `0`: no lead
- `ComfortBandUpper`, `ComfortBandLower`: acceleration comfort band in `m/s^2`.
- `JerkUpperLimit`, `JerkLowerLimit`: jerk limits in `m/s^3`.

Possible HUD uses:

- Simple, robust lead-distance bucket using `ObjGap`.
- Display `ObjGap` beside the exact `SCC11.ACC_ObjDist` to see which one tracks the cluster better.

Risk/unknowns:

- `ObjGap` is a coarse display bucket, not a measured distance.

## FCA/front radar status data

Message: `FCA11` (`0x38d`, 909 decimal), source `FCA`.

Potentially HUD-relevant fields:

- `CF_VSM_Warn`: known DBC values:
  - `2`: FCW
  - `3`: AEB
- `FCA_Status`, `FCA_CmdAct`, `FCA_StopReq`, `FCA_DrvSetStatus`, `FCA_Failinfo`.
- `CR_VSM_DecCmd`: decel command in g.
- `CF_VSM_DecCmdAct`: decel command active.
- `FCA_RelativeVelocity`: relative velocity, scale `0.1 m/s`, offset `-25.5`.
- `FCA_TimetoCollision`: TTC, scale `10 ms`, range `0..2540 ms`.

Message: `FCA12` (`0x483`, 1155 decimal), source `FCA`.

- `FCA_USM`: user setting/menu status.
- `FCA_DrvSetState`: driver setting state.

Message: `FRT_RADAR11` (`0x4a2`, 1186 decimal), source `FCA`.

- `CF_FCA_Equip_Front_Radar`: front radar equipment flag/status.

Possible HUD uses:

- FCW/AEB warning state.
- TTC during warnings.
- FCA relative velocity while the FCA module is tracking a threat.
- Front radar equipment/status indicator to validate hardware presence.

Risk/unknowns:

- Creta current code only switches AEB/FCW source to `FCA11` if `0x38d` is seen in fingerprint; otherwise it uses SCC12.
- FCA signals may only be meaningful during warning/threat situations, not during normal lead following.

## Lead vehicle departure alert

Message: `SCC13` (`0x50a`, 1290 decimal), source `SCC`.

Potentially HUD-relevant fields:

- `SCC_Equip`: SCC equipment present.
- `AebDrvSetStatus`: AEB driver setting status.
- `Lead_Veh_Dep_Alert_USM`: lead vehicle departure alert setting/status.

Possible HUD uses:

- Low-priority debug indicator for lead departure alert availability/settings.

## Raw Mando front radar tracks, not currently enabled for Creta

The generic Hyundai `RadarInterface` supports a Mando front radar DBC when the platform DBC map has `Bus.radar`.

Expected message range:

- `RADAR_TRACK_500` through `RADAR_TRACK_51f`, 32 messages.
- Bus: parser uses bus `1`.
- Rate: `50 Hz` messages, batched until `0x51f` is seen.

Fields per track:

- `STATE`: valid when `3` or `4`.
- `LONG_DIST`: longitudinal distance, scale `0.1 m`, range `0..204.7 m`.
- `REL_SPEED`: relative speed, scale `0.01 m/s`, range about `-81.92..81.92`.
- `REL_ACCEL`: relative acceleration, scale `0.02 m/s^2`, range about `-10.24..10.22`.
- `AZIMUTH`: bearing, scale `0.2 deg`, range about `-102.4..102.2 deg`.
- Other fields: `UNKNOWN_1`, `ZEROS`, `COUNTER`, `STATE_2`, `STATE_3`.

The current parser converts valid tracks into `RadarData.RadarPoint`:

- `dRel = cos(azimuth) * LONG_DIST`
- `yRel = -0.5 * sin(azimuth) * LONG_DIST`
- `vRel = REL_SPEED`
- `aRel = REL_ACCEL`
- `measured = True`

Possible HUD uses:

- Closest lead distance/speed from actual radar points.
- Count of valid tracks.
- Debug display of closest track: `dRel`, `yRel`, `vRel`, `aRel`.

Risk/unknowns:

- Creta does not currently set `HyundaiFlags.MANDO_RADAR`, so this path is off.
- We need a live fingerprint/CAN capture to confirm `0x500..0x51f` exists on bus 1.
- Enabling this may require adding the generated DBC to the platform config and ensuring safety/radar behavior remains sane.
- The `yRel` conversion has an existing Hyundai-specific `0.5` factor, so lateral position should be treated as approximate.

## Raw Mando corner radar tracks, not currently integrated

There is a generator for `hyundai_kia_mando_corner_radar`.

Potential data:

- Metadata messages: `0x100`, `0x200`.
- Radar points messages: `0x101`, `0x201`.
- Checksum messages: `0x104`, `0x204`.
- Up to 65 points, 20 Hz, 5 points per message.
- Named point fields include:
  - `DISTANCE`
  - `REL_VELOCITY`
  - `AZIMUTH`
  - many unknown `SIGNAL_*` fields

Possible HUD uses:

- Probably not useful for the main HUD unless we specifically want blindspot/cross-traffic debug.

Risk/unknowns:

- No current Hyundai parser in this branch consumes these messages.
- Creta known firmware only lists forward radar, not corner radar.
- The decoded layout is much less mature than front radar/SCC signals.

## Suggested first HUD candidates

Start with fields already decoded from `hyundai_kia_generic`, because they require no DBC/platform change:

1. `SCC11.ObjValid`
2. `SCC11.ACC_ObjDist`
3. `SCC11.ACC_ObjRelSpd`
4. `SCC11.ACC_ObjLatPos`
5. `SCC14.ObjGap`
6. `SCC11.SCCInfoDisplay`
7. `SCC12.ACCMode`
8. `FCA11.FCA_TimetoCollision` and `FCA11.FCA_RelativeVelocity`, only if `FCA11` is present

Suggested debug HUD line:

```text
RAD obj=1 d=32.4m v=-1.2 y=0.4 gap=4 scc=enabled info=0
```

Suggested next validation step:

- Add a small logger/HUD overlay for the SCC fields above.
- Record whether `FCA11`, `FRT_RADAR11`, and `0x500..0x51f` are actually present on the Creta route.
- Only after confirming `0x500` radar tracks exist should we consider enabling `MANDO_RADAR` for this platform.

## Implemented validation overlay

This branch publishes a Creta radar debug payload from `card` on `customReservedRawData0` at 10 Hz and renders it as a compact HUD line.

The HUD now also draws the word `radar` before any debug payload is received. This is a simple visual marker to confirm the radar HUD code is present and running.

The branch uses the same opendbc submodule commit as the base `creta-v11` branch so car recognition stays aligned with the other Creta v11 branches. Detailed SCC/FCA parsed values are optional; when they are not available from `CarState`, the payload still includes raw CAN presence flags gathered in `card.py`.

Displayed fields when detailed parsed SCC/FCA data is available:

- `SCC11.ObjValid`
- `SCC11.ACC_ObjDist`
- `SCC11.ACC_ObjRelSpd`
- `SCC11.ACC_ObjLatPos`
- `SCC14.ObjGap`
- `SCC12.ACCMode`
- `SCC11.SCCInfoDisplay`
- `FCA11.CF_VSM_Warn`
- `FCA11.FCA_TimetoCollision`

Presence flags in the same payload:

- `scc11_seen`
- `scc12_seen`
- `scc14_seen`
- `fca11_seen`
- `frt_radar11_seen`
- `raw_mando_front_seen`
