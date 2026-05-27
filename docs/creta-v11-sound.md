# Creta v11 Sound Change

## Summary

The `creta-v11-sound` branch removes the Tizi-specific engage and disengage sound override from `selfdrive/ui/soundd.py`.

## Behavior

Before this change, devices identified as `tizi` replaced the standard sounds with:

- `engage_tizi.wav`
- `disengage_tizi.wav`

After this change, Tizi devices use the same default sounds as the rest of the UI:

- `engage.wav`
- `disengage.wav`

All other alert sounds are unchanged.

## Files Changed

- `selfdrive/ui/soundd.py`

## Validation

The branch was tested on the target setup and the engage/disengage audio behavior works as expected.
