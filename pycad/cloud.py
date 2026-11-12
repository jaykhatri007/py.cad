"""Explicit WebDAV uploads/downloads with revision guards and bounded responses."""

import base64
import json
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QFileDialog,
    QInputDialog,
)
from . import appsettings
from .native_io import document_to_dict, document_from_dict, atomic_write

LIMIT = 32 * 1024 * 1024
POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pycad-webdav")
DAV = "{DAV:}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError(
            "Cloud address redirects; configure the final WebDAV collection URL"
        )


class WebDAVClient:
    def __init__(self, url, username="", password=""):
        p = urllib.parse.urlsplit(url.strip())
        if p.username or p.password or p.query or p.fragment or not p.hostname:
            raise ValueError(
                "Use a collection URL without credentials, query or fragment"
            )
        if p.scheme != "https" and not (
            p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1", "::1")
        ):
            raise ValueError("Use HTTPS; HTTP is supported for localhost development")
        try:
            p.port
        except ValueError as ex:
            raise ValueError("Invalid server port") from ex
        if any(ord(c) < 32 for c in url + username + password):
            raise ValueError("Invalid connection fields")
        self.url = urllib.parse.urlunsplit(
            (p.scheme, p.netloc, p.path.rstrip("/") + "/", "", "")
        )
        self.auth = (
            "Basic " + base64.b64encode((username + ":" + password).encode()).decode()
            if username or password
            else ""
        )
        self.opener = urllib.request.build_opener(NoRedirect())

    def file_url(self, name):
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 160
            or name in (".", "..")
            or any(c in name for c in "/\\")
            or any(ord(c) < 32 for c in name)
        ):
            raise ValueError("Use a single file name, without folder paths")
        if Path(name).suffix.lower() not in (".pycad", ".html", ".zip"):
            raise ValueError("Cloud files support .pycad, .html and .zip")
        return self.url + urllib.parse.quote(name, safe="")

    def request(self, method, url, data=None, headers=None, limit=LIMIT):
        h = {"User-Agent": "PY.cad/16.5.0", **(headers or {})}
        if self.auth:
            h["Authorization"] = self.auth
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with self.opener.open(req, timeout=15) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise ValueError("Cloud response exceeds supported size")
                return body, dict(response.headers)
        except urllib.error.HTTPError as ex:
            if ex.code == 412:
                raise ValueError(
                    "Cloud file changed or already exists; refresh or upload under a new name"
                ) from ex
            raise ValueError(f"Cloud request failed (HTTP {ex.code})") from ex
        except urllib.error.URLError as ex:
            raise ValueError(
                "Cannot reach cloud server; check its address, certificate and connection"
            ) from ex

    def list_files(self):
        body = b'<?xml version="1.0"?><D:propfind xmlns:D="DAV:"><D:prop><D:resourcetype/><D:getetag/><D:getcontentlength/></D:prop></D:propfind>'
        raw, _ = self.request(
            "PROPFIND",
            self.url,
            body,
            {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
            2 * 1024 * 1024,
        )
        guard = raw.replace(b"\x00", b"").upper()
        if b"<!DOCTYPE" in guard or b"<!ENTITY" in guard:
            raise ValueError("Unsupported cloud XML declaration")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as ex:
            raise ValueError("Server did not return a WebDAV file listing") from ex
        entries = []
        for item in root.findall(DAV + "response"):
            href = item.findtext(DAV + "href", "")
            url = urllib.parse.urljoin(self.url, href)
            base = urllib.parse.urlsplit(self.url)
            target = urllib.parse.urlsplit(url)
            if (base.scheme, base.netloc) != (
                target.scheme,
                target.netloc,
            ) or not target.path.startswith(base.path):
                continue
            rest = urllib.parse.unquote(target.path[len(base.path) :])
            try:
                self.file_url(rest)
            except ValueError:
                continue
            for propstat in item.findall(DAV + "propstat"):
                if " 200 " not in propstat.findtext(DAV + "status", "") + " ":
                    continue
                prop = propstat.find(DAV + "prop")
                if prop is None or prop.find(".//" + DAV + "collection") is not None:
                    continue
                etag = prop.findtext(DAV + "getetag", "")
                if len(etag) > 256 or any(ord(c) < 32 for c in etag):
                    continue
                try:
                    size = int(prop.findtext(DAV + "getcontentlength", "0"))
                except ValueError:
                    size = 0
                entries.append(dict(name=rest, etag=etag, size=max(0, size)))
        return sorted(entries, key=lambda e: e["name"].casefold())

    def upload(self, name, raw, etag=None):
        if len(raw) > LIMIT:
            raise ValueError("Cloud file exceeds 32 MiB")
        if etag and (
            etag.startswith("W/") or len(etag) > 256 or any(ord(c) < 32 for c in etag)
        ):
            raise ValueError(
                "A strong server revision tag is required to replace a file"
            )
        h = (
            {"Content-Type": "application/octet-stream", "If-Match": etag}
            if etag
            else {"Content-Type": "application/octet-stream", "If-None-Match": "*"}
        )
        return self.request("PUT", self.file_url(name), raw, h, 1024 * 1024)

    def download(self, name):
        raw, headers = self.request("GET", self.file_url(name))
        if Path(name).suffix.lower() == ".pycad":
            try:
                document_from_dict(json.loads(raw))
            except (ValueError, UnicodeError) as ex:
                raise ValueError("Downloaded native drawing is invalid") from ex
        return raw, headers


class CloudManager(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.pending = None
        self.files = []
        self.setWindowTitle("Cloud files / WebDAV")
        self.resize(560, 460)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        s = appsettings.get_settings()
        self.url = QLineEdit(s.value("cloud/url", ""))
        self.url.setPlaceholderText("https://server.example/webdav/collection/")
        self.username = QLineEdit(s.value("cloud/username", ""))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Collection URL", self.url)
        form.addRow("Username", self.username)
        form.addRow("Password (session only)", self.password)
        self.list = QListWidget()
        root.addWidget(self.list)
        self.status = QLabel(
            "Configure your WebDAV server, then Refresh. Passwords are not saved."
        )
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        row = QHBoxLayout()
        root.addLayout(row)
        self.actions = []
        for label, fn in (
            ("Refresh", self.refresh),
            ("Upload drawing…", self.upload_drawing),
            ("Upload view…", self.upload_view),
            ("Download…", self.download),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, cb=fn: self.perform(cb))
            row.addWidget(b)
            self.actions.append(b)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        root.addWidget(close)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)

    def client(self):
        client = WebDAVClient(
            self.url.text(), self.username.text(), self.password.text()
        )
        s = appsettings.get_settings()
        s.setValue("cloud/url", client.url)
        s.setValue("cloud/username", self.username.text())
        return client

    def perform(self, fn):
        try:
            fn()
        except ValueError as ex:
            self.status.setText(str(ex))

    def submit(self, fn, callback):
        if self.pending:
            return
        self.callback = callback
        self.pending = POOL.submit(fn)
        self.status.setText("Working…")
        for b in self.actions:
            b.setEnabled(False)
        self.timer.start()

    def poll(self):
        if not self.pending or not self.pending.done():
            return
        future = self.pending
        self.pending = None
        self.timer.stop()
        for b in self.actions:
            b.setEnabled(True)
        try:
            self.callback(future.result())
        except (ValueError, OSError) as ex:
            self.status.setText(str(ex))

    def refresh(self):
        c = self.client()
        self.submit(c.list_files, self.show_files)

    def show_files(self, files):
        self.files = files
        self.list.clear()
        self.list.addItems([f"{e['name']} · {e['size']:,} bytes" for e in files])
        self.status.setText(
            f"{len(files)} files. Revision guards protect existing files."
        )

    def upload_bytes(self, raw, extension):
        c = self.client()
        default = (
            Path(self.mw.document.filepath).stem
            if self.mw.document.filepath
            else "drawing"
        )
        name, ok = QInputDialog.getText(
            self, "Upload snapshot", "Remote file name:", text=default + extension
        )
        if not ok:
            return
        c.file_url(name)
        if Path(name).suffix.lower() != extension:
            raise ValueError("Use a " + extension + " file name")
        old = next((e for e in self.files if e["name"] == name), None)
        if old and not old["etag"]:
            raise ValueError("Server provides no revision tag; upload under a new name")
        self.submit(
            lambda: c.upload(name, raw, old["etag"] if old else None),
            lambda result: self.status.setText(
                "Uploaded snapshot: " + name + ". Refresh to retrieve its new revision."
            ),
        )

    def upload_drawing(self):
        payload = document_to_dict(self.mw.document)
        document_from_dict(payload)
        raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.upload_bytes(raw, ".pycad")

    def upload_view(self):
        from .collaboration import shared_view_html

        self.upload_bytes(shared_view_html(self.mw.document).encode(), ".html")

    def download(self):
        row = self.list.currentRow()
        if row < 0:
            raise ValueError("Select a cloud file first")
        entry = self.files[row]
        c = self.client()
        if entry["size"] > LIMIT:
            raise ValueError("Cloud download exceeds 32 MiB")
        path, _ = QFileDialog.getSaveFileName(self, "Download copy", entry["name"])
        if not path:
            return

        def finish(result):
            raw, _ = result
            atomic_write(path, lambda output: Path(output).write_bytes(raw))
            self.status.setText("Downloaded copy: " + Path(path).name)

        self.submit(lambda: c.download(entry["name"]), finish)

    def done(self, result):
        self.timer.stop()
        if self.pending:
            self.pending.cancel()
        self.password.clear()
        super().done(result)


def cloud_manager(mw):
    dialog = CloudManager(mw)
    try:
        dialog.exec()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()
