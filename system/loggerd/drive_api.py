"""Google Drive API uploader using a device-granted drive.file token."""
import json
import mimetypes
from pathlib import Path
from urllib import parse, request

from openpilot.system.loggerd.drive_oauth import access_token

FILES_API = "https://www.googleapis.com/drive/v3/files"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"


def call(url, method="GET", body=None, content_type=None):
  headers = {"Authorization": "Bearer " + access_token()}
  if content_type:
    headers["Content-Type"] = content_type
  req = request.Request(url, data=body, headers=headers, method=method)
  with request.urlopen(req, timeout=90) as resp:
    result = resp.read()
    return json.loads(result) if result else {}


def query_children(parent, name):
  escaped = name.replace("\\", "\\\\").replace("'", "\\'")
  q = f"name = '{escaped}' and '{parent}' in parents and trashed = false"
  url = FILES_API + "?" + parse.urlencode({"q": q, "fields": "nextPageToken,files(id,name,mimeType)", "page_size": 100})
  response = call(url)
  return response.get("files", [])


def ensure_folder(parent, name):
  for child in query_children(parent, name):
    if child.get("mimeType") == "application/vnd.google-apps.folder":
      return child["id"]
  payload = json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder",
                        "parents": [parent]}).encode()
  response = call(FILES_API + "?fields=id", "POST", payload, "application/json")
  return response["id"]


def upload(path: Path, segment: str):
  # This app creates its own OpenPilot directory, which is the scope's boundary
  # for its own data; drive.file does not grant access to arbitrary user files.
  folder = ensure_folder("root", "OpenPilot")
  folder = ensure_folder(folder, segment)
  existing = query_children(folder, path.name)
  matching = [item for item in existing if item.get("mimeType") != "application/vnd.google-apps.folder"]
  if matching:
    # Replace only a file previously visible to this application.
    method = "PATCH"
    url = UPLOAD_API + "/" + parse.quote(matching[0]["id"]) + "?uploadType=resumable"
    metadata = b"{}"
  else:
    method = "POST"
    url = UPLOAD_API + "?uploadType=resumable"
    metadata = json.dumps({"name": path.name, "parents": [folder]}).encode()
  headers = {
    "Authorization": "Bearer " + access_token(),
    "Content-Type": "application/json; charset=UTF-8",
    "X-Upload-Content-Type": "application/octet-stream",
    "X-Upload-Content-Length": str(path.stat().st_size),
  }
  init = request.Request(url, data=metadata, headers=headers, method=method)
  with request.urlopen(init, timeout=90) as response:
    session = response.headers["Location"]

  size = path.stat().st_size
  # Chunks must be multiples of 256 KiB, except the final chunk.
  chunk = 1024 * 1024
  sent = 0
  with path.open("rb") as source:
    while sent < size:
      data = source.read(chunk)
      end = sent + len(data) - 1
      headers = {"Content-Type": "application/octet-stream",
                 "Content-Range": f"bytes {sent}-{end}/{size}"}
      req = request.Request(session, data=data, headers=headers, method="PUT")
      try:
        with request.urlopen(req, timeout=120) as response:
          response.read()
          if end + 1 == size and response.status not in (200, 201):
            raise RuntimeError("Drive did not finalize the upload")
      except __import__("urllib").error.HTTPError as exc:
        if exc.code != 308:
          raise
      sent = end + 1
  if size == 0:
    req = request.Request(session, data=b"", headers={"Content-Range": "bytes */0"}, method="PUT")
    with request.urlopen(req, timeout=90) as response:
      if response.status not in (200, 201):
        raise RuntimeError("Drive did not finalize empty upload")
