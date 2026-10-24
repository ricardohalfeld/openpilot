#!/usr/bin/env python3
"""Optional WireGuard peer supervision for comma 3X.

A pre-installed wg-quick and kernel WireGuard support are required.
No private keys are stored in this repository.
"""
import os
from pathlib import Path
import shutil
import subprocess
import time

CONFIG = Path("/data/wireguard/wg0.conf")
INTERFACE = "wg0"
RETRY_SECONDS = 30


def installed():
  return shutil.which("wg") is not None and shutil.which("wg-quick") is not None


def active():
  try:
    result = subprocess.run(["wg", "show", "interfaces"], capture_output=True,
                            text=True, timeout=5, check=False)
    return result.returncode == 0 and INTERFACE in result.stdout.split()
  except OSError:
    return False


def start():
  if not CONFIG.is_file() or not installed():
    return False
  if (CONFIG.stat().st_mode & 0o077) != 0:
    return False  # Never allow a world-readable private key.
  if active():
    return True
  try:
    subprocess.run(["wg-quick", "up", str(CONFIG)], check=True, timeout=30,
                   capture_output=True)
    return active()
  except (OSError, subprocess.SubprocessError):
    return False


def main():
  while True:
    start()
    time.sleep(RETRY_SECONDS)


if __name__ == "__main__":
  main()
