#!/usr/bin/env python3
"""Regression tests for Drive-upload retention and queue selection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpilot.system.loggerd import drive_upload, deleter


class TestDriveUpload(unittest.TestCase):
  def test_completed_logs_are_not_pending(self):
    with tempfile.TemporaryDirectory() as tmp:
      segment = "2026-10-24--09-00-00--0"
      folder = Path(tmp) / segment
      folder.mkdir()
      logfile = folder / "qlog.zst"
      logfile.write_bytes(b"qlog")
      stat = logfile.stat()
      state = {f"{segment}/qlog.zst": [stat.st_size, stat.st_mtime_ns]}
      with patch.object(deleter.Paths, "log_root", return_value=tmp):
        self.assertFalse(deleter.drive_upload_pending(segment, state, set()))
        self.assertTrue(deleter.drive_upload_pending(segment, {}, set()))

  def test_selected_video_is_pending(self):
    with tempfile.TemporaryDirectory() as tmp:
      segment = "2026-10-24--09-00-00--0"
      route = segment.rsplit("--", 1)[0]
      folder = Path(tmp) / segment
      folder.mkdir()
      video = folder / "fcamera.hevc"
      video.write_bytes(b"video")
      with patch.object(deleter.Paths, "log_root", return_value=tmp):
        self.assertFalse(deleter.drive_upload_pending(segment, {}, set()))
        self.assertTrue(deleter.drive_upload_pending(segment, {}, {route}))

  def test_wifi_guard_fail_closed(self):
    with patch.object(drive_upload.HARDWARE, "get_network_type", side_effect=RuntimeError):
      self.assertFalse(drive_upload.wifi_connected())


if __name__ == "__main__":
  unittest.main()
