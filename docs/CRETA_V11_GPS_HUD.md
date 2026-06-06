# Creta v11 GPS HUD diagnostics

This branch adds GPS source and fix diagnostics to the onroad HUD to make speed-source selection visible while driving.

## GPS services shown on the HUD

The HUD distinguishes between two GPS location services:

- `gpsLocationExternal`, shown as `EXT`
- `gpsLocation`, shown as `GPS`

`gpsLocationExternal` was initially expected to be the preferred GPS source for the HUD speed override. During road testing on this branch, however, the display showed no usable external GPS signal. The working GPS signal was present on the local/base `gpsLocation` service instead.

Because of that observed result, the HUD now checks both services:

1. Use `gpsLocationExternal` if it is alive, valid, and reports a fix.
2. Otherwise use `gpsLocation` if it is alive, valid, and reports a fix.
3. Otherwise fall back to odometry/cluster speed.

The displayed speed-source label follows the same order:

- `GPS EXT` means speed is coming from `gpsLocationExternal`.
- `GPS` means speed is coming from local/base `gpsLocation`.
- `ODOMETRY` means neither GPS service currently has a usable fix, so speed is coming from vehicle odometry/cluster data.

## Observed test result

A drive was performed with clear local GPS availability. The original implementation stayed on `ODOMETRY` because it only considered `gpsLocationExternal` as a usable GPS source. The diagnostic HUD later showed that the external GPS path was not providing a usable signal, while the local/base GPS service was the one carrying the live fix data.

After adding `gpsLocation` to the UI subscription and fallback logic, the HUD correctly identified the local GPS service and the speed source switched away from odometry when local GPS had a usable fix.

This confirms that, for the tested Creta v11 setup, local/base GPS is the active GPS path and external GPS should not be assumed to be present.

## HUD field reference

Example display:

```text
GPS
EXT never A0 V0 F0 SAT--
GPS 0.1s A1 V1 F1 SAT14
EXT H-- S--   GPS H1.5 S0.1
TS E-- G0.1s   SIG n/a
```

### Speed source

The first line is the selected speed source:

- `GPS EXT`: using `gpsLocationExternal.speed`
- `GPS`: using `gpsLocation.speed`
- `ODOMETRY`: using `carState.vEgoCluster` if available, otherwise `carState.vEgo`

### Service status lines

Each GPS service has a status line:

```text
EXT never A0 V0 F0 SAT--
GPS 0.1s A1 V1 F1 SAT14
```

Fields:

- `EXT`: status for `gpsLocationExternal`
- `GPS`: status for `gpsLocation`
- `0.1s`: time since the UI last received a message from that service
- `never`: no message has arrived for that service since the current onroad runtime started
- `A1` / `A0`: SubMaster reports the service alive / not alive
- `V1` / `V0`: SubMaster reports the message valid / invalid
- `F1` / `F0`: usable fix / no usable fix. This is true only when the service is alive, valid, and `hasFix` is true
- `SAT14`: satellite count reported by the GPS message
- `SAT--`: no satellite count available from that service

### Accuracy line

```text
EXT H-- S--   GPS H1.5 S0.1
```

Fields:

- `H`: horizontal accuracy in meters
- `S`: speed accuracy in meters per second
- `--`: no positive value reported

In the observed working case, `GPS H... S...` showed useful values while `EXT H-- S--` did not, matching the conclusion that the local/base GPS service was active and the external GPS service was not.

### Timestamp line

```text
TS E-- G0.1s   SIG n/a
```

Fields:

- `TS`: timestamp age from the GPS payload itself, when available
- `E`: payload timestamp age for `gpsLocationExternal`
- `G`: payload timestamp age for `gpsLocation`
- `--`: no usable payload timestamp
- `SIG n/a`: signal strength is not exposed through `GpsLocationData`, so the HUD cannot show GNSS signal strength/CN0 from these messages

## Practical interpretation while driving

For the tested setup, the expected healthy local-GPS case is:

```text
GPS
EXT never A0 V0 F0 SAT--
GPS <small age> A1 V1 F1 SAT<positive count>
```

That indicates that no external GPS source is active, but local GPS is alive, valid, has a fix, and is being used for the HUD speed value.

A problematic case is:

```text
ODOMETRY
EXT never A0 V0 F0 SAT--
GPS never A0 V0 F0 SAT--
```

That means neither GPS path has delivered a usable message during the current onroad runtime, so the HUD remains on odometry.
