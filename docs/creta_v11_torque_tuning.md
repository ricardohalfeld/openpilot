# Creta V11 torque tuning notes

This branch tunes Hyundai Creta V11 lateral control using the torque controller in
`selfdrive/controls/lib/latcontrol_torque.py`.

## Control-law data flow

The lateral torque controller does not run the PID directly in steering-torque
space. It runs the feedback loop in lateral-acceleration space, then converts the
result to steering torque at the end.

Per control update:

1. Current steering angle is converted to measured curvature:

   ```text
   measured_curvature = -VM.calc_curvature(radians(steeringAngleDeg - angleOffsetDeg), vEgo, roll)
   ```

2. Measured curvature is converted to actual lateral acceleration:

   ```text
   measurement = measured_curvature * vEgo^2
   ```

3. Desired curvature is converted to future desired lateral acceleration:

   ```text
   future_desired_lateral_accel = desired_curvature * vEgo^2
   ```

4. The desired lateral acceleration is delayed through the request buffer to
   match lateral actuator delay:

   ```text
   setpoint = lat_accel_request_buffer[-delay_frames]
   error = setpoint - measurement
   ```

5. Roll compensation is removed from feedforward:

   ```text
   roll_compensation = roll * g
   ff = future_desired_lateral_accel - roll_compensation
   ```

6. `latAccelOffset` is subtracted from feedforward:

   ```text
   ff -= latAccelOffset
   ```

7. Friction compensation is added to feedforward:

   ```text
   ff += get_friction(error + JERK_GAIN * desired_lateral_jerk,
                      lateral_accel_deadzone,
                      FRICTION_THRESHOLD,
                      torque_params)
   ```

8. PID feedback is computed in lateral-acceleration space:

   ```text
   output_lataccel = pid.update(error, speed=vEgo, feedforward=ff,
                                freeze_integrator=freeze_integrator)
   ```

9. The requested lateral acceleration is converted to steering torque:

   ```text
   output_torque = torque_from_lateral_accel(output_lataccel, torque_params)
   ```

10. The sign is inverted before returning the command:

   ```text
   return -output_torque
   ```

## Meaning of the tuned parameters

### `latAccelFactor`

`latAccelFactor` is the main slope between lateral acceleration and steering
torque. In simplified terms, it defines how much lateral acceleration the car is
expected to produce per unit of steering torque, or equivalently how much torque
is required for a desired lateral acceleration after the conversion function is
applied.

Effect in the control law:

- It is used by `torque_from_lateral_accel(...)` to convert the PID result from
  lateral acceleration into steering torque.
- It is used by `lateral_accel_from_torque(...)` when computing PID limits from
  `steer_max`.
- If it is too aggressive, the same lateral-acceleration request produces too
  much steering torque and can amplify steering-wheel motion.
- If it is too weak, the controller needs more feedback correction and can lag or
  oscillate because the actuator is always catching up.

### `latAccelOffset`

`latAccelOffset` is a feedforward bias correction. In this branch it is applied
immediately after roll compensation:

```text
ff = future_desired_lateral_accel - roll_compensation - latAccelOffset
```

Effect in the control law:

- It compensates for persistent bias between device roll compensation and the
  vehicle's real lateral response.
- It shifts the feedforward request before PID feedback is added.
- It should not be used to fix high-frequency steering-wheel shake. It is a DC or
  low-frequency bias term.

### `friction`

`friction` is used by `get_friction(...)` to add a direction-dependent boost to
feedforward when the requested correction is outside the lateral-acceleration
deadzone.

Effect in the control law:

- It helps overcome static steering friction near zero command.
- The sign is driven by `error + JERK_GAIN * desired_lateral_jerk`, not just by
  raw desired curvature.
- If too low, the wheel may stick, release late, and require feedback correction.
- If too high, the wheel can receive alternating kicks around zero and develop a
  limit-cycle oscillation.

### PID gains

The torque tune parameters above are not the only source of oscillation. This
controller also has fixed proportional and integral gains:

```text
KP = 0.8
KI = 0.15
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, KP]
INTERP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
```

At low speed, proportional gain is intentionally much higher. A bump can inject a
fast steering-angle disturbance that appears as lateral-acceleration error. If
that disturbance falls inside a frequency band where EPS, tire compliance, and
controller phase delay line up, changing only `latAccelFactor` and `friction` may
not remove the oscillation.

## Why a bump can still excite steering oscillation

A road bump can create a short steering-angle impulse through tire, suspension,
rack, and EPS compliance. The controller sees this as a measured lateral
acceleration deviation. If the controller responds with torque of the opposite
sign, then overshoots, the EPS/wheel system can enter a limit cycle.

The important signature is not just high torque. It is alternating steering-wheel
motion after an impulse while the desired curvature remains relatively smooth.

Typical signature:

- `desiredCurvature` or `desiredLateralAccel` is smooth.
- `steeringAngleDeg` changes sign repeatedly or rings around a local value.
- `steeringTorque` / command torque alternates sign with the wheel motion.
- `actualLateralAccel - desiredLateralAccel` oscillates in a narrow band.
- The event starts shortly after a vertical road disturbance, bump, lane seam, or
  steering rack kick.

## Proposed oscillation detector

Add a runtime monitor inside `LatControlTorque` that watches steering-wheel angle
and commanded torque over a short moving window.

Use three conditions together to avoid false positives:

1. **Oscillation energy**

   Band-pass or high-pass the steering angle around the target frequency range.
   A practical first implementation can avoid a full filter and use recent
   samples directly:

   ```text
   angle_hp = steeringAngleDeg - moving_average(steeringAngleDeg, 0.5 s)
   angle_energy = rms(angle_hp over 0.4-0.8 s)
   ```

2. **Repeated sign changes**

   Count zero crossings in `angle_hp` or in `steeringRateDeg`:

   ```text
   sign_changes >= 3 within 0.5 s
   ```

3. **Controller is feeding the oscillation**

   Check whether commanded torque is phase-aligned with the oscillatory steering
   velocity in a way that injects energy:

   ```text
   mean(output_torque * steeringRateDeg) > threshold
   ```

   Positive correlation means the controller is, on average, pushing in the
   direction of steering-wheel motion instead of damping it.

Suggested initial gate:

```text
active
vEgo > 5 m/s
abs(desired_lateral_jerk) < jerk_quiet_threshold
angle_energy > angle_energy_threshold
sign_changes >= 3 over 0.5 s
mean(output_torque * steeringRateDeg) > energy_injection_threshold
not steeringPressed
```

The `desired_lateral_jerk` gate is important: it prevents the detector from
triggering during real path curvature transitions.

## Proposed mitigation

When oscillation is detected, do not immediately disengage. First enter a short
oscillation-damping mode.

Recommended first mitigation:

1. Freeze the PID integrator.
2. Temporarily reduce proportional correction.
3. Temporarily reduce or disable friction compensation.
4. Add a small damping term opposite steering rate.
5. Ramp the normal controller back in after the oscillation energy decays.

Conceptually:

```text
if oscillation_detected:
  freeze_integrator = True
  friction_scale = 0.0 to 0.3
  kp_scale = 0.3 to 0.6
  damping_torque = -osc_damping_gain * steeringRateDeg
else:
  friction_scale -> 1.0 with ramp
  kp_scale -> 1.0 with ramp
  damping_torque -> 0.0 with ramp
```

Apply the damping in torque space after converting the PID result:

```text
output_torque = torque_from_lateral_accel(output_lataccel, torque_params)
output_torque += damping_torque
```

Then apply the usual steering torque limits and sign convention.

## Minimal implementation sequence

1. Log the detector features first without changing control:

   - high-pass steering angle RMS
   - steering-rate zero-crossing count
   - `output_torque * steeringRateDeg` moving mean
   - detector boolean

2. Replay or drive over known bump cases and confirm that the detector fires only
   on real ringing events.

3. Enable integrator freeze only.

4. Add friction scaling.

5. Add proportional scaling.

6. Add damping torque last, with conservative limits.

This order makes the change easy to validate and keeps the first active
intervention reversible if the detector is too sensitive.

## Initial thresholds to try

These are placeholders for on-road validation, not final calibration:

```text
osc_window_s = 0.6
angle_average_s = 0.5
min_v_ego = 5.0 m/s
min_zero_crossings = 3
angle_energy_threshold = 0.15 deg RMS
energy_injection_threshold = small positive value after log review
osc_hold_s = 0.5
osc_recovery_s = 1.0
friction_scale_during_osc = 0.2
kp_scale_during_osc = 0.5
```

The threshold most worth deriving from data is `energy_injection_threshold`,
because it separates harmless steering-wheel vibration from controller-amplified
oscillation.
