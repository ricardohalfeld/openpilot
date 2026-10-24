#!/usr/bin/env python3
"""Offroad Google Drive uploader. Requires a locally configured rclone binary."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from cereal import log
from openpilot.system.hardware import HARDWARE
from openpilot.system.hardware.hw import Paths

STATE_DIR = Path("/data/drive_upload")
STATE_PATH = STATE_DIR / "state.json"
SELECT_PATH = STATE_DIR / "video_routes.json"
CONFIG_PATH = STATE_DIR / "rclone.conf"
RCLONE = "/data/drive_upload/rclone"
REMOTE = "drive:openpilot"
LOG_NAMES = ("rlog.zst", "qlog.zst")
VIDEO_NAMES = ("fcamera.hevc", "dcamera.hevc", "ecamera.hevc")
MIN_IDLE_SECONDS = 120


def read_json(path, fallback):
  try:
    return json.loads(path.read_text())
  except (OSError, ValueError):
    return fallback


def write_json(path, value):
  STATE_DIR.mkdir(parents=True, exist_ok=True)
  tmp = path.with_suffix(".tmp")
  tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
  os.replace(tmp, path)


def selected_routes():
  data = read_json(SELECT_PATH, [])
  return set(data) if isinstance(data, list) else set()


def set_video_route(route, enabled):
  routes = selected_routes()
  if enabled:
    routes.add(route)
  else:
    routes.discard(route)
  write_json(SELECT_PATH, sorted(routes))


def eligible_files():
  root = Path(Paths.log_root())
  selected = selected_routes()
  if not root.exists():
    return []
  now = time.time()
  logs, videos = [], []
  for seg in root.iterdir():
    if not seg.is_dir() or "--" not in seg.name:
      continue
    if any(seg.glob("*.lock")):
      continue
    try:
      if now - seg.stat().st_mtime < MIN_IDLE_SECONDS:
        continue
    except OSError:
      continue
    route = seg.name.rsplit("--", 1)[0]
    for name in LOG_NAMES:
      file = seg / name
      if file.is_file():
        logs.append((seg.name, file))
    if route in selected:
      for name in VIDEO_NAMES:
        file = seg / name
        if file.is_file():
          videos.append((seg.name, file))
  return sorted(logs) + sorted(videos)


def upload_one(segment, path):
  # Never invoke a shell, and never keep authentication material in Git.
  if not CONFIG_PATH.is_file() or not Path(RCLONE).is_file():
    return False
  dest = f"{REMOTE}/{segment}/{path.name}"
  try:
    subprocess.run([RCLONE, "--config", str(CONFIG_PATH),
                    "--transfers", "1", "--checkers", "1",
                    "--retries", "2", "--timeout", "90s",
                    "copyto", str(path), dest],
                   timeout=900, check=True, capture_output=True)
    return True
  except (OSError, subprocess.SubprocessError):
    return False


def wifi_connected():
  # Hardware network type distinguishes Wi-Fi from cellular transport.
  try:
    return HARDWARE.get_network_type() == log.DeviceState.NetworkType.wifi
  except Exception:
    return False


def run_once():
  # Uploading while driving is intentionally disabled.
  from openpilot.common.params import Params
  if Params().get_bool("IsOnroad") or not wifi_connected():
    return
  state = read_json(STATE_PATH, {})
  for segment, path in eligible_files():
    if Params().get_bool("IsOnroad") or not wifi_connected():
      break
    key = f"{segment}/{path.name}"
    try:
      stat = path.stat()
    except OSError:
      continue
    fingerprint = [stat.st_size, stat.st_mtime_ns]
    if state.get(key) == fingerprint:
      continue
    if not upload_one(segment, path):
      break  # Preserve FIFO ordering and retry next time.
    state[key] = fingerprint
    write_json(STATE_PATH, state)


def main():
  parser = argparse.ArgumentParser()
  commands = parser.add_subparsers(dest="command")
  video = commands.add_parser("video", help="Select a route for video upload")
  video.add_argument("route")
  video.add_argument("action", choices=("on", "off"))
  commands.add_parser("once")
  args = parser.parse_args()
  if args.command == "video":
    if "/" in args.route or chr(92) in args.route or ".." in args.route or not args.route:
      parser.error("Provide a route ID, not a segment or path")
    set_video_route(args.route, args.action == "on")
    return
  if args.command == "once":
    run_once()
    return
  while True:
    try:
      run_once()
    except Exception:
      # Keep this ancillary service from impacting manager.
      import traceback
      traceback.print_exc()
    time.sleep(60)


if __name__ == "__main__":
  main()
