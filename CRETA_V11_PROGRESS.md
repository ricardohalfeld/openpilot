# Creta v11 Working Notes

This documents the current working Hyundai Creta setup on openpilot `v0.11.0`.

## Working Branches

openpilot fork:

```text
repo:   ricardohalfeld/openpilot
branch: creta-v11
head:   84ede7026cd1f7ba47128742abc8412098ef1ed9
```

opendbc fork:

```text
repo:   ricardohalfeld/opendbc
branch: creta-dbc-v11
head:   ac2abfc47a567b4e3affe44fcf93d0eb6883d18e
```

## Install

On the comma 3X custom software screen, enter:

```text
ricardohalfeld/creta-v11
```

Full installer URL:

```text
installer.comma.ai/ricardohalfeld/creta-v11
```

## Current Result

The `creta-v11` build installs, boots, and recognizes the Hyundai Creta.

The car is recognized without needing an EPS firmware fingerprint entry.

## openpilot State

`creta-v11` is based on:

```text
openpilot tag:    v0.11.0
openpilot commit: 3469d9aadbc16eb854bad3d851bd580d2b8f132e
```

The `opendbc` submodule URL points to the personal fork:

```ini
[submodule "opendbc"]
  path = opendbc_repo
  url = ../../ricardohalfeld/opendbc.git
```

The `opendbc_repo` submodule points to:

```text
ac2abfc47a567b4e3affe44fcf93d0eb6883d18e
```

## opendbc Creta Changes

The compatible Creta DBC branch is based on the openpilot `v0.11.0` opendbc baseline and adds the Creta support changes in:

```text
opendbc/car/hyundai/fingerprints.py
opendbc/car/hyundai/hyundaican.py
opendbc/car/hyundai/values.py
opendbc/car/torque_data/override.toml
```

The platform added is:

```text
HYUNDAI_CRETA_2ND_GEN
```

## UI and Debug Additions

The onroad HUD now shows the identified platform fingerprint from:

```text
CarParams.carFingerprint
```

EPS firmware/debug details are written to:

```text
CarEpsFingerprint
```

Retrieve it on-device with:

```bash
cat /data/params/d/CarEpsFingerprint
```

or:

```bash
cd /data/openpilot
python -m openpilot.common.params CarEpsFingerprint
```

## Verification Commands

On the comma 3X:

```bash
cd /data/openpilot
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git submodule status opendbc_repo
cat /data/params/d/CarEpsFingerprint 2>/dev/null
```

Expected branch:

```text
creta-v11
```

Expected `opendbc_repo` commit:

```text
ac2abfc47a567b4e3affe44fcf93d0eb6883d18e
```

## Push Notes

If Git LFS tries to upload old LFS objects and GitHub rejects the push, skip the LFS push hook.

PowerShell:

```powershell
$env:GIT_LFS_SKIP_PUSH='1'; git push halfeld creta-v11
```

Bash:

```bash
GIT_LFS_SKIP_PUSH=1 git push halfeld creta-v11
```
