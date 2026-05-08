# Creta Flag Matrix

This note maps the Hyundai-specific openpilot/opendbc car flags in the current `creta-v11` stack to the 2024 Hyundai Creta platform now fingerprinting as `HYUNDAI_CRETA_2ND_GEN`.

Scope:

- These are `HyundaiFlags` from [opendbc_repo/opendbc/car/hyundai/values.py](D:/Software/openpilot/opendbc_repo/opendbc/car/hyundai/values.py:71).
- This is about the current Creta integration path in this repo, not every Hyundai in openpilot.
- "Possible" means the code structure allows it for this platform.
- "Impossible" means the current platform architecture rules it out.
- "Unknown" means we need live CAN or firmware evidence before deciding.

## What we know now

- The Creta entry is a plain non-CAN-FD platform with no static flags assigned in [opendbc_repo/opendbc/car/hyundai/values.py](D:/Software/openpilot/opendbc_repo/opendbc/car/hyundai/values.py:169).
- openpilot already fingerprints and boots this car successfully on the classic Hyundai path, so the whole `CANFD*` branch is not the right family for this platform.
- The firmware set shows a forward camera and a forward radar ECU, but firmware presence alone does not tell us whether SCC is camera-based or radar-based for openpilot purposes.
- The current car appears to be an ICE Creta, not hybrid/EV/FCEV.

## Observed Runtime State

Captured on `2026-05-08`:

```json
{"carFingerprint": "HYUNDAI_CRETA_2ND_GEN", "alphaLongitudinalAvailable": true, "openpilotLongitudinalControl": false, "pcmCruise": true, "radarUnavailable": true, "flags": 16777600, "flagsHex": "0x1000180", "safetyParam": 0, "safetyParamHex": "0x0"}
```

Decoded current dynamic flags:

- `0x80` -> `SEND_LFA`
- `0x100` -> `USE_FCA`
- `0x1000000` -> `HAS_LDA_BUTTON`

What that lets us say with more confidence:

- `SEND_LFA` is not just possible; it is already being set on the current car.
- `USE_FCA` is not just possible; it is already being set on the current car.
- `HAS_LDA_BUTTON` is not just possible; it is already being set on the current car.
- `HYBRID`, `EV`, and `FCEV` are not active on this car.
- `radarUnavailable=true` means openpilot currently does not see a supported radar interface on the expected path, even though radar firmware was successfully queried.

## Matrix

| Flag | Creta status | Why |
|---|---|---|
| `CANFD_LKA_STEERING` | Impossible | Only used on CAN-FD Hyundai platforms. The current Creta integration is classic CAN, not CAN-FD. |
| `CANFD_ALT_BUTTONS` | Impossible | Same reason: CAN-FD-only detection and message layout. |
| `CANFD_ALT_GEARS` | Impossible | CAN-FD-only gear message variant. |
| `CANFD_CAMERA_SCC` | Impossible | CAN-FD-only SCC routing flag. |
| `ALT_LIMITS` | Possible | This is a steering torque/limit tuning choice, not a bus architecture constraint. It may be needed if stock steering torque behavior matches the higher-torque group. |
| `ENABLE_BLINKERS` | Possible but unproven | The code supports it, but it is not part of the current Creta config and is usually relevant to architectures where extra ECU disable logic is needed. |
| `CANFD_ALT_GEARS_2` | Impossible | CAN-FD-only alternate gear parsing path. |
| `SEND_LFA` | Active on current car | On classic Hyundai this is set dynamically if CAN message `0x485` is seen on bus 2. Current runtime flags already include it. |
| `USE_FCA` | Active on current car | On classic Hyundai this is set dynamically if message `0x38d` is present, meaning AEB/FCW state should be read from `FCA11` instead of `SCC12`. Current runtime flags already include it. |
| `CANFD_LKA_STEERING_ALT` | Impossible | Alternate CAN-FD LKA steering layout; not relevant on classic CAN Creta. |
| `HYBRID` | Impossible for the current car | The current Creta target is an ICE vehicle. If you later target a different Creta hybrid variant, that would be a separate platform question. |
| `EV` | Impossible for the current car | Same reason: not an EV Creta target. |
| `MANDO_RADAR` | Unknown | This depends on whether radar point output on bus 1 matches the Mando-radar assumption. Needs live CAN evidence, typically message `0x500` on bus 1. |
| `CANFD` | Impossible | The current platform is not CAN-FD. |
| `RADAR_SCC` | Possible | This is one of the key open questions for long control. If SCC authority lives in radar rather than camera, this flag may be correct. Needs live behavior evidence. |
| `CAMERA_SCC` | Possible | Also plausible. Only one of `RADAR_SCC` or `CAMERA_SCC` should describe the production path, and we need CAN behavior to know which one. |
| `CHECKSUM_CRC8` | Possible | This affects classic Hyundai steering message checksum generation in `LKAS11`. Your CRC8 memory is plausible here. Many newer classic Hyundai platforms use CRC8. Needs live acceptance testing. |
| `CHECKSUM_6B` | Possible | Also a valid classic Hyundai checksum family, but mutually exclusive with CRC8. Only one checksum mode should be true. |
| `LEGACY` | Very unlikely, effectively impossible for this platform | `LEGACY` is for older Hyundai safety modes missing counters/checksums. A 2024 Creta on the modern classic-CAN path is not a realistic fit for that bucket. |
| `UNSUPPORTED_LONGITUDINAL` | Possible as a temporary truth value | This flag does not describe hardware family; it is an integration-confidence gate. If long is not validated yet, marking it unsupported is valid until proven otherwise. |
| `CANFD_NO_RADAR_DISABLE` | Impossible | CAN-FD-only limitation related to ADAS ECU communication control. |
| `CLUSTER_GEARS` | Possible | Classic Hyundai gear parsing can come from the cluster on some cars. Need live message evidence or a parsing mismatch to justify it. |
| `TCU_GEARS` | Possible | Also plausible on classic Hyundai. Only one gear-source strategy should win in the final config. |
| `MIN_STEER_32_MPH` | Possible | This is a lateral behavior constraint used on some classic Hyundai platforms. It depends on how the Creta behaves at lower speed, not on architecture. |
| `HAS_LDA_BUTTON` | Active on current car | On classic Hyundai this is set dynamically if message `0x391` is present, indicating the LFA/LDA steering-wheel button path. Current runtime flags already include it. |
| `FCEV` | Impossible for the current car | Not a fuel-cell Creta target. |
| `ALT_LIMITS_2` | Possible but unlikely | This is a more specialized steering-limit tuning bucket. Possible in code, but nothing yet points to the Creta needing it. |

## Best current read

Flags that are structurally ruled out for this Creta:

- `CANFD_LKA_STEERING`
- `CANFD_ALT_BUTTONS`
- `CANFD_ALT_GEARS`
- `CANFD_CAMERA_SCC`
- `CANFD_ALT_GEARS_2`
- `CANFD_LKA_STEERING_ALT`
- `CANFD`
- `CANFD_NO_RADAR_DISABLE`
- `HYBRID`
- `EV`
- `FCEV`

Flags that feel most likely to matter next:

- `RADAR_SCC` vs `CAMERA_SCC`
- `CHECKSUM_CRC8` vs `CHECKSUM_6B` vs neither
- `CLUSTER_GEARS` vs `TCU_GEARS`
- `MIN_STEER_32_MPH`
- `UNSUPPORTED_LONGITUDINAL` as a temporary gate until long is proven

Flags already established by the device snapshot:

- `SEND_LFA`
- `USE_FCA`
- `HAS_LDA_BUTTON`

## CRC8 note

Your CRC8 hunch is very reasonable, but it is mainly a steering-message compatibility question, not the whole long-control story by itself.

In this codebase:

- `CHECKSUM_CRC8` and `CHECKSUM_6B` change how [hyundaican.py](D:/Software/openpilot/opendbc_repo/opendbc/car/hyundai/hyundaican.py:84) computes the `LKAS11` checksum.
- That matters for whether steering commands are accepted cleanly.
- Longitudinal success still depends on separate questions like SCC ownership, radar/camera routing, and whether disabling the stock longitudinal ECU path works as expected.

So CRC8 is a strong candidate to validate, but not the only thing to validate.

## Practical next flags to test

If we want the shortest path to a better Creta config, the next things to introspect or experimentally pin down are:

1. Whether the car is `RADAR_SCC` or `CAMERA_SCC`.
2. Whether `USE_FCA` is required.
3. Which steering checksum family applies: `CHECKSUM_CRC8`, `CHECKSUM_6B`, or default.
4. Whether gear parsing wants `CLUSTER_GEARS` or `TCU_GEARS`.
5. Whether low-speed steering requires `MIN_STEER_32_MPH`.

That set will tell us much more than trying random long-control flags first.
