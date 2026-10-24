# Creta v11 — Google Drive experimental uploader

This branch uses **Google OAuth device authorization**, not a Google password or rclone.
The Google Drive API accepts the `drive.file` scope for the limited-input device flow:
https://developers.google.com/identity/protocols/oauth2/limited-input-device

## Implemented
- Offroad, Wi-Fi-only background queue for rlog/qlog and opt-in camera clips.
- Google device authorization request, polling, refresh tokens, stored under `/data/drive_upload/`.
- Direct resumable uploads with Google Drive API into app-created OpenPilot/segment folders.
- Persistent successful-upload ledger; deletion priority favors fully uploaded segments.
- Tests in `system/loggerd/test_drive_upload.py` (not yet run on the comma).

## One-time Google Cloud configuration (required)
A Google Cloud project must have Google Drive API enabled and an OAuth client
of type **TVs and Limited Input devices**. The project's OAuth consent screen
must be configured for the intended Google account and publishing/testing rules.
Put ONLY the OAuth **client ID** into `/data/drive_upload/client_id`. The client
ID is public, not your Google password. Do not commit tokens or credentials.
Protect `/data/drive_upload/google_token.json` (mode 0600).

## Pairing (current CLI prototype)
On the comma, offroad with Wi-Fi, execute:

```sh
cd /data/openpilot
python3 -m openpilot.system.loggerd.drive_oauth pair
```

It prints Google's verification URL and the one-time user code. Open the URL on
your phone, log in to Google, authorize `drive.file`, then sign out from your
phone if desired. The comma retains a refresh token, not your password.
`python3 -m openpilot.system.loggerd.drive_oauth status` shows whether a token
file exists; it does NOT check whether the token was revoked.

## Videos (CLI prototype)
```sh
python3 -m openpilot.system.loggerd.drive_upload video 'ROUTE-ID' on
python3 -m openpilot.system.loggerd.drive_upload video 'ROUTE-ID' off
```

## Limitations and safety
- **No pairing or video checkbox exists in the comma UI yet**. The CLI method
  still requires shell access. SSH-free pairing is not complete.
- No OAuth client ID has been provisioned, and no authorization has been performed.
- Automatic uploads run only while offroad with Wi-Fi. In-progress transfers
  may continue briefly while the process is being stopped by manager.
- The API transfer implementation and the tests have not been validated on comma 3X.
- Cleanup can still remove pending logs to prevent a full disk.
- The `drive.file` scope limits accessible files, but is **not a true
  folder-level access restriction** enforced by Google. The app chooses to
  operate within its own OpenPilot folder.
- The upload ledger records a successful response, not an independent checksum
  verification from Google.
- Do not use this experimental branch for daily driving without on-device checks.
