# Alert Sound Notes

This note documents where the openpilot engage/disengage sounds live in this repo and a starting shortlist of softer replacement references.

## Asset Locations

Core sound playback logic:

- [selfdrive/ui/soundd.py](selfdrive/ui/soundd.py)

Sound asset directory:

- [selfdrive/assets/sounds](selfdrive/assets/sounds)

Current sound files in that directory:

- [engage.wav](selfdrive/assets/sounds/engage.wav)
- [disengage.wav](selfdrive/assets/sounds/disengage.wav)
- [engage_tizi.wav](selfdrive/assets/sounds/engage_tizi.wav)
- [disengage_tizi.wav](selfdrive/assets/sounds/disengage_tizi.wav)
- [refuse.wav](selfdrive/assets/sounds/refuse.wav)
- [prompt.wav](selfdrive/assets/sounds/prompt.wav)
- [prompt_distracted.wav](selfdrive/assets/sounds/prompt_distracted.wav)
- [warning_soft.wav](selfdrive/assets/sounds/warning_soft.wav)
- [warning_immediate.wav](selfdrive/assets/sounds/warning_immediate.wav)

Sound generation script for the default non-Tizi engage/disengage beeps:

- [make_beeps.py](selfdrive/assets/sounds/make_beeps.py)

## Which Files Are Used

In [soundd.py](selfdrive/ui/soundd.py), the default mapping is:

- `AudibleAlert.engage` -> `engage.wav`
- `AudibleAlert.disengage` -> `disengage.wav`

On Tizi hardware, the mapping changes to:

- `AudibleAlert.engage` -> `engage_tizi.wav`
- `AudibleAlert.disengage` -> `disengage_tizi.wav`

So for a normal comma 3X path, the main files to replace or regenerate are:

- [engage.wav](selfdrive/assets/sounds/engage.wav)
- [disengage.wav](selfdrive/assets/sounds/disengage.wav)

## Current Sound Shape

The default generated engage/disengage sounds are simple decaying sine beeps created in [make_beeps.py](selfdrive/assets/sounds/make_beeps.py):

- `engage.wav` uses frequency `1661.219 Hz`
- `disengage.wav` uses frequency `1318.51 Hz`
- both are generated at `48000 Hz`
- both are mono 16-bit WAV files

That means a replacement asset should ideally stay:

- mono
- 16-bit PCM WAV
- `48000 Hz`
- short

## Replacement Direction

Goal:

- keep engage clearly recognizable
- make engage less chirpy and less like a sharp chime
- keep disengage noticeable for safety, but less grating

The best replacement style is probably:

- engage: soft click, muted tap, or light UI tick
- disengage: slightly firmer click or short double-tick

I would avoid:

- long musical chimes
- sounds with a lot of decay
- sounds that are too quiet or too similar between engage and disengage

## Reference Candidates

These are references to audition, not a final recommendation yet.

1. Pixabay, "Interface Soft Click":
   - https://pixabay.com/sound-effects/interface-soft-click-131438/
   - Very short and understated. Good candidate shape for engage.

2. Pixabay, "UI Click Soft":
   - https://pixabay.com/sound-effects/technology-ui-click-soft-512213/
   - Newer minimal UI-style click. Worth auditioning for engage.

3. Pixabay, "Soft UI Pop - light, minimal click":
   - https://pixabay.com/sound-effects/soft-ui-pop-light-minimal-click-451232/
   - Slightly softer and more synthetic. Could work if trimmed very short.

4. Mixkit click sound library:
   - https://mixkit.co/free-sound-effects/click/
   - Useful pool for finding a firmer disengage click.

## Practical Plan

If we decide to actually change the sounds, the safest order is:

1. audition a few soft click references
2. make or trim two short WAV assets:
   - softer engage
   - firmer disengage
3. keep the filenames the same first:
   - `engage.wav`
   - `disengage.wav`
4. leave alert logic in [soundd.py](selfdrive/ui/soundd.py) unchanged
5. test on-device for:
   - volume
   - recognizability
   - whether disengage is still unmistakable
