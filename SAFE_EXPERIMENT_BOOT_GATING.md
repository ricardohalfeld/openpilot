# Safe Experiment Boot Gating

This note describes a recovery-friendly way to ship risky UI or debug experiments without turning the device into a reset machine.

## Goal

Default behavior in the repo should be safe.

That means:

- risky code should **not** run by default
- a normal boot should behave as if the experiment is off
- the experiment should only run after it is explicitly armed by the user

The desired property is:

- if an experiment crashes the UI or breaks boot flow, the next boot should come up safe automatically

## Correct Default

Yes: the risky code path should be `false` by default in the repo.

It should only become active after a deliberate action such as:

- a settings toggle
- a param write over SSH
- a one-shot "try on next boot" command

So the base rule is:

- **safe by default**
- **armed only on purpose**

## Recommended Pattern

Use a one-shot boot gate rather than a plain always-on persistent toggle.

### Suggested params

Two-param version:

- `CustomFeatureEnabled`
  - persistent
  - means: user wants this feature available in principle

- `CustomFeatureArmed`
  - persistent
  - means: allow this feature to run on the next boot

### Boot behavior

At startup:

1. read `CustomFeatureArmed`
2. immediately set `CustomFeatureArmed = false`
3. only run the risky code if the param was true when read
4. after the app reaches a known-good stable point, set `CustomFeatureArmed = true` again

Result:

- if boot succeeds, the feature re-arms itself for next boot
- if boot fails before the stable point, the feature stays off next boot

That gives one automatic fallback step without losing the ability to keep testing.

## Why Not Just One Persistent Toggle?

If you use only one persistent toggle and leave it on:

- a crashing experiment can crash every boot

If you use only one persistent toggle and clear it at startup:

- it works as a one-shot switch
- but it mixes together:
  - "I want this feature"
  - "try it on this boot"

That can still be okay, but two params are cleaner when you want long-term control.

## Simpler One-Param Version

If the goal is just "try this next boot, and fall back safely if it fails", a one-param version is enough:

- `TryCustomFeatureNextBoot`

Flow:

1. read `TryCustomFeatureNextBoot`
2. immediately clear it to `false`
3. if it was true, run the experiment
4. once stable, set it back to `true`

This is simple and effective for UI experiments.

## Good Re-Arm Point

The feature should be re-armed only after a clearly safe checkpoint.

Good examples:

- after the UI main layout is alive
- after required model/state subscriptions are valid enough
- after the first successful render/update cycle

Bad examples:

- during imports
- at the top of startup before the risky code has actually survived
- before the dependent UI state is available

The rule is:

- re-arm only after the code has already demonstrated a safe initial boot

## Best Use Cases

This pattern is a good fit for:

- custom HUD elements
- experimental debug overlays
- model/radar visualization
- new onroad UI widgets
- UI features that may throw on missing state

Less ideal for:

- deep manager startup changes
- code that crashes before params can be read
- low-level system initialization work

## Practical Workflow

Desired workflow:

1. repo boots with experiment off
2. user explicitly arms the experiment
3. reboot or restart the relevant process
4. experiment runs
5. if it survives startup, it re-arms itself
6. if it crashes before the stable point, next boot is safe automatically

This gives:

- intentional testing
- automatic fallback
- no repeated full reset cycle

## Recommendation

For risky UI work, the safest repo policy is:

- default off in the repo
- explicit user arming required
- immediately clear the arm flag at startup
- re-arm only after a successful stable boot point

That is the right strategy for "only try when we want to, and live to try another boot."
