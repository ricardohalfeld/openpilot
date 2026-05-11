# Creta Torque Tuning Notes

This note captures a conservative first-pass recommendation for Hyundai Creta lateral torque tuning based on current driving impressions.

Current active override values in [override.toml](D:/Software/openpilot/opendbc_repo/opendbc/car/torque_data/override.toml):

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.5, 2.5, 0.1]
```

Meaning:

- `LAT_ACCEL_FACTOR = 2.5`
- `MAX_LAT_ACCEL_MEASURED = 2.5`
- `FRICTION = 0.1`

## Driving Impressions To Address

Observed impressions:

- steering seems to stick a bit
- after a pothole or disturbance, the controller oscillates a bit

Interpretation:

- "sticks a bit" suggests friction compensation may be too low
- "oscillates after a disturbance" suggests the effective steering gain may be a bit too high

## Conservative First Suggestion

Recommended first test:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.35, 2.5, 0.12]
```

Changes:

- lower `LAT_ACCEL_FACTOR` from `2.5` to `2.35`
- leave `MAX_LAT_ACCEL_MEASURED` at `2.5`
- raise `FRICTION` from `0.1` to `0.12`

## Why This Is Conservative

### Lower `LAT_ACCEL_FACTOR` slightly

From:

```text
2.5 -> 2.35
```

Reason:

- reduces controller aggressiveness a bit
- may help calm post-disturbance oscillation
- small enough to avoid turning the car dull immediately

### Increase `FRICTION` slightly

From:

```text
0.10 -> 0.12
```

Reason:

- adds a little more compensation for steering stickiness / deadzone
- may improve small corrections near center
- small enough to avoid making the steering feel jumpy

### Leave `MAX_LAT_ACCEL_MEASURED` unchanged

Reason:

- current complaint is about feel and response, not lateral authority ceiling
- changing too many variables at once makes interpretation harder

## If That First Test Helps

If the first change helps but does not go far enough:

next small step could be:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.25, 2.5, 0.13]
```

That would be the next rung down in gain and up in friction.

## If The First Test Goes The Wrong Way

### If it becomes too sluggish

- `LAT_ACCEL_FACTOR` was reduced too much
- move it back upward slightly, for example:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.4, 2.5, 0.12]
```

### If it becomes too twitchy around center

- `FRICTION` may have gone too high
- bring friction back down slightly, for example:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.35, 2.5, 0.11]
```

### If oscillation remains mostly unchanged

- the gain reduction may not have been enough
- try the second-step candidate:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.25, 2.5, 0.12]
```

## Testing Advice

Change only one candidate line at a time and restart the relevant processes or reboot so the cached torque parameters are reloaded.

When evaluating, pay attention to:

- lane centering smoothness on straight roads
- recovery after bumps / potholes
- small corrections near center
- curve entry confidence
- whether the car feels dull versus natural

## Recommendation

Best first test:

```toml
"HYUNDAI_CRETA_2ND_GEN" = [2.35, 2.5, 0.12]
```

That is the most reasonable low-risk first move given the current subjective report.
