# Creta v11 Torque Tune UI

## Summary

The `creta-v11-tune` branch adds an onroad torque tuning panel for cars using torque lateral control.

The panel lets the driver adjust persistent override values from the UI and lets `controlsd` apply the active override while driving.

## UI Behavior

The HUD shows a `TORQUE TUNE` panel when the loaded `CarParams` lateral tuning type is `torque`.

Controls:

- `LAT`: adjusts `latAccelFactor` in `0.05` steps.
- `F`: adjusts `friction` in `0.01` steps.
- `MAX`: adjusts `maxLatAccel` in `0.10` steps.
- `RST`: removes the override and returns the UI to the values from `CarParams`.

The panel, values, and buttons were enlarged after initial testing so the controls are easier to see and tap on-device.

## Stored Param

The UI writes the override to the persistent, non-logged JSON param:

- `TorqueTuneOverride`

Example shape:

```json
{
  "enabled": true,
  "latAccelFactor": 2.5,
  "friction": 0.08,
  "maxLatAccel": 2.8
}
```

## Applied Control Values

`controlsd` polls `TorqueTuneOverride` every `0.2` seconds.

When enabled and valid, it applies:

- `latAccelFactor`
- `friction`

The override is range-checked before use:

- `latAccelFactor`: `1.5` to `3.5`
- `friction`: `0.0` to `0.25`

`maxLatAccel` is currently persisted and displayed by the UI, but it is not applied by `controlsd` in this branch.

## Files Changed

- `common/params_keys.h`
- `selfdrive/controls/controlsd.py`
- `selfdrive/ui/onroad/hud_renderer.py`

## Validation

The UI panel has been checked visually and responds to button presses. Live tuning behavior still needs road validation.
