# Google Drive upload (experimental)

This branch starts from `creta-v11` and adds an **offroad-only** background uploader.
It does not alter vehicle control.

## What is implemented
- Scans completed, unlocked route segments under `Paths.log_root()`.
- Uploads `qlog.zst` and `rlog.zst` first, oldest segment first.
- Optionally uploads camera files for routes selected in `/data/drive_upload/video_routes.json`.
- Keeps a persistent upload ledger in `/data/drive_upload/state.json`.
- Retries incomplete transfers on the next pass; never stores credentials in source control.
- Runs only while the manager reports the vehicle offroad; rechecks between files.

## Initial setup on comma 3X
Place an **ARM64-compatible** `rclone` executable at `/data/drive_upload/rclone`, make it executable, and provide `/data/drive_upload/rclone.conf` (permissions 0600).

Configure an OAuth Google Drive remote named `drive` on another trusted computer using `rclone config` and a Google OAuth client configured for the minimum practical permissions (prefer `drive.file`). Follow rclone's headless authorization procedure; transfer the configuration to the comma device over a trusted SSH connection. Never place OAuth secrets, access tokens, or refresh tokens in Git.

Destination: `drive:openpilot/<segment>/<filename>`.

## Route video selection
Until an on-device checkbox is added, select a route via:

```sh
cd /data/openpilot
python3 -m openpilot.system.loggerd.drive_upload video 'YYYY-MM-DD--HH-MM-SS' on
python3 -m openpilot.system.loggerd.drive_upload video 'YYYY-MM-DD--HH-MM-SS' off
```

Pass the route ID without its trailing segment number.

## Known limitations / safety
- **UI checkbox is not implemented yet.**
- **This does not modify the existing deleter.** Under storage pressure, openpilot may delete logs before they have uploaded. Do not rely on this branch as a lossless archival system yet.
- Upload is attempted only offroad; it does not explicitly check whether the transport is Wi-Fi, and therefore could use another available internet connection.
- The initial rclone binary and OAuth configuration must be installed manually.
- `rclone copyto` is retried after interruption. The ledger avoids repeat transfers of unchanged local files after confirmed success.
- Untested on physical comma 3X. Validate resource usage and manager integration before daily driving.
