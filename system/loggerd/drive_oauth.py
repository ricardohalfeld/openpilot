#!/usr/bin/env python3
"""Google device OAuth for comma. No Google password is stored on the device.

Provision /data/drive_upload/client_id with an OAuth client ID of type
'TVs and Limited Input devices'. Google Drive API must be enabled.
"""
import argparse
import json
import os
from pathlib import Path
import time
from urllib import parse, request, error

ROOT = Path("/data/drive_upload")
CLIENT_FILE = ROOT / "client_id"
CLIENT_SECRET_FILE = ROOT / "client_secret"
TOKEN_FILE = ROOT / "google_token.json"
DEVICE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"


def post_form(url, fields):
  data = parse.urlencode(fields).encode()
  req = request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
  try:
    with request.urlopen(req, timeout=20) as response:
      return json.load(response)
  except error.HTTPError as exc:
    body = exc.read()
    try:
      return json.loads(body)
    except ValueError:
      raise RuntimeError("OAuth request failed") from exc


def client_id():
  value = CLIENT_FILE.read_text().strip()
  if not value:
    raise RuntimeError("Empty Google OAuth client ID")
  return value


def client_secret():
  value = CLIENT_SECRET_FILE.read_text().strip()
  if not value:
    raise RuntimeError("Empty Google OAuth client secret")
  return value


def save_token(data):
  if not data.get("refresh_token"):
    raise RuntimeError("Google did not issue a refresh token")
  ROOT.mkdir(parents=True, exist_ok=True)
  os.chmod(ROOT, 0o700)
  saved = {"refresh_token": data["refresh_token"], "access_token": data["access_token"],
           "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60}
  tmp = TOKEN_FILE.with_suffix(".tmp")
  fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
  with os.fdopen(fd, "w") as stream:
    json.dump(saved, stream)
  os.replace(tmp, TOKEN_FILE)
  os.chmod(TOKEN_FILE, 0o600)


def begin_pairing():
  response = post_form(DEVICE_ENDPOINT, {"client_id": client_id(), "scope": SCOPE})
  if "device_code" not in response:
    raise RuntimeError(f"Device authorization failed: {response.get('error', 'unknown')}")
  return response


def finish_pairing(info, on_code=print):
  on_code(f"Abra {info['verification_url']} e digite o codigo {info['user_code']}")
  interval = max(5, int(info.get("interval", 5)))
  deadline = time.monotonic() + int(info["expires_in"])
  while time.monotonic() < deadline:
    time.sleep(interval)
    result = post_form(TOKEN_ENDPOINT, {"client_id": client_id(),
                       "client_secret": client_secret(),
                       "device_code": info["device_code"],
                       "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
    if "access_token" in result:
      save_token(result)
      return True
    code = result.get("error")
    if code == "slow_down":
      interval += 5
    elif code not in ("authorization_pending",):
      raise RuntimeError(f"Authorization stopped: {code or 'unknown'}")
  raise TimeoutError("Authorization expired")


def access_token():
  data = json.loads(TOKEN_FILE.read_text())
  if data.get("access_token") and data.get("expires_at", 0) > time.time():
    return data["access_token"]
  result = post_form(TOKEN_ENDPOINT, {"client_id": client_id(), "client_secret": client_secret(),
                     "refresh_token": data["refresh_token"],
                     "grant_type": "refresh_token"})
  if "access_token" not in result:
    raise RuntimeError(f"Token refresh failed: {result.get('error', 'unknown')}")
  result["refresh_token"] = data["refresh_token"]
  save_token(result)
  return result["access_token"]


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("command", choices=("pair", "status"))
  args = parser.parse_args()
  if args.command == "pair":
    finish_pairing(begin_pairing())
    print("Google Drive autorizado. Nenhuma senha foi armazenada.")
  else:
    print("Google Drive autorizado" if TOKEN_FILE.is_file() else "Google Drive nao autorizado")


if __name__ == "__main__":
  main()
