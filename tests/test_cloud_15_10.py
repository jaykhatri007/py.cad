"""Exercise WebDAV over real localhost HTTP, including revision conflicts."""

import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit
import pytest
from PyQt6.QtTest import QTest
from pycad.cloud import WebDAVClient, CloudManager
from pycad.document import Document
from pycad.native_io import document_to_dict
from pycad import appsettings


@pytest.fixture
def dav_server():
    state = {"files": {}, "requests": [], "xml": None}

    def etag(raw):
        return '"' + hashlib.sha256(raw).hexdigest() + '"'

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def response(self, status, body=b"", headers=None):
            self.send_response(status)
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def record(self):
            state["requests"].append((self.command, self.path, dict(self.headers)))

        def do_PROPFIND(self):
            self.record()
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if state["xml"] is not None:
                self.response(207, state["xml"])
                return
            rows = [
                "<D:response><D:href>/dav/</D:href><D:propstat><D:prop><D:resourcetype><D:collection/></D:resourcetype></D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
            ]
            for name, raw in state["files"].items():
                rows.append(
                    f"<D:response><D:href>/dav/{quote(name)}</D:href><D:propstat><D:prop><D:resourcetype/><D:getetag>{etag(raw)}</D:getetag><D:getcontentlength>{len(raw)}</D:getcontentlength></D:prop><D:status>HTTP/1.1 200 OK</D:status></D:propstat></D:response>"
                )
            self.response(
                207,
                (
                    '<D:multistatus xmlns:D="DAV:">'
                    + "".join(rows)
                    + "</D:multistatus>"
                ).encode(),
            )

        def do_PUT(self):
            self.record()
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            name = unquote(urlsplit(self.path).path.removeprefix("/dav/"))
            old = state["files"].get(name)
            if (self.headers.get("If-None-Match") == "*" and old is not None) or (
                self.headers.get("If-Match")
                and (old is None or self.headers["If-Match"] != etag(old))
            ):
                self.response(412)
                return
            state["files"][name] = raw
            self.response(201, headers={"ETag": etag(raw)})

        def do_GET(self):
            self.record()
            if self.path.endswith("redirect.html"):
                self.response(302, headers={"Location": "/elsewhere.html"})
                return
            name = unquote(urlsplit(self.path).path.removeprefix("/dav/"))
            if name not in state["files"]:
                self.response(404)
                return
            raw = state["files"][name]
            self.response(200, raw, {"ETag": etag(raw)})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/dav/", state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_actual_list_upload_revision_conflict_download(qapp, dav_server):
    url, state = dav_server
    c = WebDAVClient(url, "user", "session-secret")
    raw = json.dumps(document_to_dict(Document())).encode()
    c.upload("Room café.pycad", raw)
    listing = c.list_files()
    assert listing[0]["name"] == "Room café.pycad" and listing[0]["size"] == len(raw)
    assert c.download(listing[0]["name"])[0] == raw
    with pytest.raises(ValueError, match="changed"):
        c.upload(listing[0]["name"], raw)
    original = listing[0]["etag"]
    new = raw + b" "
    c.upload(listing[0]["name"], new, original)
    with pytest.raises(ValueError, match="changed"):
        c.upload(listing[0]["name"], raw, original)
    assert state["files"][listing[0]["name"]] == new
    assert state["requests"][0][2]["If-None-Match"] == "*"
    assert any(request[2].get("Depth") == "1" for request in state["requests"])
    assert all(
        request[2]["Authorization"].startswith("Basic ")
        for request in state["requests"]
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/dav/",
        "https://user:pw@example.com/",
        "https://example.com/?token=x",
        "https://example.com/#x",
        "file:///tmp/",
        "https://example.com:bad/",
    ],
)
def test_invalid_endpoint_rejected(url):
    with pytest.raises(ValueError):
        WebDAVClient(url)


@pytest.mark.parametrize(
    "name", ["../a.pycad", "a/b.pycad", r"a\b.pycad", "a.exe", "a.pycad\r\nX:x", ".."]
)
def test_path_rejected_before_network(name):
    c = WebDAVClient("https://example.com/dav/")
    with pytest.raises(ValueError):
        c.file_url(name)


def test_invalid_native_download_and_redirect_are_rejected(qapp, dav_server):
    url, state = dav_server
    c = WebDAVClient(url)
    state["files"]["bad.pycad"] = b"{}"
    with pytest.raises(ValueError, match="invalid"):
        c.download("bad.pycad")
    before = len(state["requests"])
    with pytest.raises(ValueError, match="redirect"):
        c.download("redirect.html")
    assert len(state["requests"]) == before + 1


@pytest.mark.parametrize(
    "xml",
    [
        b"not xml",
        b'<!DOCTYPE x [<!ENTITY a "bad">]><x/>',
        '<!DOCTYPE x [<!ENTITY a "bad">]><x/>'.encode("utf-16"),
    ],
)
def test_malformed_or_entity_xml_rejected(dav_server, xml):
    url, state = dav_server
    state["xml"] = xml
    with pytest.raises(ValueError):
        WebDAVClient(url).list_files()


def test_response_limit_and_weak_etag(dav_server):
    url, state = dav_server
    c = WebDAVClient(url)
    state["files"]["large.html"] = b"x" * 20
    with pytest.raises(ValueError, match="size"):
        c.request("GET", c.file_url("large.html"), limit=10)
    with pytest.raises(ValueError, match="strong"):
        c.upload("large.html", b"ok", 'W/"x"')
    assert state["files"]["large.html"] == b"x" * 20


def test_cloud_dialog_async_listing_and_session_only_password(
    main_window, qapp, dav_server
):
    url, state = dav_server
    state["files"]["view.html"] = b"<svg/>"
    d = CloudManager(main_window)
    d.url.setText(url)
    d.username.setText("user")
    d.password.setText("secret")
    d.refresh()
    assert d.pending is not None and all(not b.isEnabled() for b in d.actions)
    deadline = time.monotonic() + 3
    while d.pending is not None and time.monotonic() < deadline:
        QTest.qWait(20)
    assert d.pending is None and d.files[0]["name"] == "view.html"
    s = appsettings.get_settings()
    assert s.value("cloud/url") == url and all(
        "password" not in key for key in s.allKeys()
    )
    d.reject()
    assert not d.password.text() and not d.timer.isActive()


def test_cloud_close_cancels_ui_callback(main_window):
    from concurrent.futures import Future

    d = CloudManager(main_window)
    d.pending = Future()
    d.password.setText("secret")
    d.timer.start()
    d.reject()
    assert d.pending.cancelled() and not d.timer.isActive() and not d.password.text()
