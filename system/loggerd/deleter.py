#!/usr/bin/env python3
import os
import shutil
import threading
from pathlib import Path
from openpilot.system.loggerd.drive_upload import read_json, STATE_PATH, selected_routes, LOG_NAMES, VIDEO_NAMES
from openpilot.system.hardware.hw import Paths
from openpilot.common.swaglog import cloudlog
from openpilot.system.loggerd.config import get_available_bytes, get_available_percent
from openpilot.system.loggerd.uploader import listdir_by_creation
from openpilot.system.loggerd.xattr_cache import getxattr

MIN_BYTES = 5 * 1024 * 1024 * 1024
MIN_PERCENT = 10

DELETE_LAST = ['boot', 'crash']

PRESERVE_ATTR_NAME = 'user.preserve'
PRESERVE_ATTR_VALUE = b'1'
PRESERVE_COUNT = 5


def has_preserve_xattr(d: str) -> bool:
  return getxattr(os.path.join(Paths.log_root(), d), PRESERVE_ATTR_NAME) == PRESERVE_ATTR_VALUE


def get_preserved_segments(dirs_by_creation: list[str]) -> set[str]:
  # skip deleting most recent N preserved segments (and their prior segment)
  preserved = set()
  for n, d in enumerate(filter(has_preserve_xattr, reversed(dirs_by_creation))):
    if n == PRESERVE_COUNT:
      break
    date_str, _, seg_str = d.rpartition("--")

    # ignore non-segment directories
    if not date_str:
      continue
    try:
      seg_num = int(seg_str)
    except ValueError:
      continue

    # preserve segment and two prior
    for _seg_num in range(max(0, seg_num - 2), seg_num + 1):
      preserved.add(f"{date_str}--{_seg_num}")

  return preserved


def drive_upload_pending(segment: str, state: dict, selected: set[str]) -> bool:
  folder = Path(Paths.log_root()) / segment
  route = segment.rsplit("--", 1)[0]
  names = LOG_NAMES + (VIDEO_NAMES if route in selected else ())
  for name in names:
    path = folder / name
    try:
      stat = path.stat()
    except OSError:
      continue
    if state.get(f"{segment}/{name}") != [stat.st_size, stat.st_mtime_ns]:
      return True
  return False


def deleter_thread(exit_event: threading.Event):
  while not exit_event.is_set():
    out_of_bytes = get_available_bytes(default=MIN_BYTES + 1) < MIN_BYTES
    out_of_percent = get_available_percent(default=MIN_PERCENT + 1) < MIN_PERCENT

    if out_of_percent or out_of_bytes:
      dirs = listdir_by_creation(Paths.log_root())
      preserved_dirs = get_preserved_segments(dirs)
      upload_state = read_json(STATE_PATH, {})
      video_routes = selected_routes()
      # Prefer removing fully backed-up segments first. Never risk a full disk:
      # the original retention/deletion policy still applies under pressure.

      # remove the earliest directory we can
      for delete_dir in sorted(dirs, key=lambda d: (d in DELETE_LAST, d in preserved_dirs, drive_upload_pending(d, upload_state, video_routes))):
        delete_path = os.path.join(Paths.log_root(), delete_dir)

        if any(name.endswith(".lock") for name in os.listdir(delete_path)):
          continue

        try:
          cloudlog.info(f"deleting {delete_path}")
          shutil.rmtree(delete_path)
          break
        except OSError:
          cloudlog.exception(f"issue deleting {delete_path}")
      exit_event.wait(.1)
    else:
      exit_event.wait(30)


def main():
  deleter_thread(threading.Event())


if __name__ == "__main__":
  main()
