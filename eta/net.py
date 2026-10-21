"""HTTP for the launcher: JSON / bytes with a proper User-Agent and certifi's CA bundle (python.org builds have no
system certificates), a thread pool that hands results back to the Qt thread, and an icon cache on disk."""
import hashlib
import json
import ssl
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from . import __version__
from .paths import data_dir

USER_AGENT = f"tearsmilk/eta-launcher/{__version__} (github.com/tearsmilk/amkawa-lang)"


def _context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_CTX = _context()


class NetError(Exception):
    pass


def get_bytes(url, timeout=20, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        raise NetError(_explain(e)) from e


def get_json(url, timeout=20, params=None):
    return json.loads(get_bytes(url, timeout, params).decode("utf-8"))


def download(url, dest, timeout=60, progress=None, cancel=None, chunk=1 << 16):
    """Stream url → dest (via a .part file). progress(done_bytes, total_bytes); cancel() → True aborts."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r, open(tmp, "wb") as fh:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if cancel and cancel():
                    raise NetError("Отменено")
                buf = r.read(chunk)
                if not buf:
                    break
                fh.write(buf)
                done += len(buf)
                if progress:
                    progress(done, total)
        tmp.replace(dest)
        return dest
    except NetError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise NetError(_explain(e)) from e


def _explain(e):
    text = str(e)
    if "CERTIFICATE" in text.upper():
        return "Не удалось проверить сертификат сайта"
    if "timed out" in text.lower():
        return "Сервер не ответил вовремя"
    if "Name or service not known" in text or "nodename nor servname" in text or "getaddrinfo" in text:
        return "Нет подключения к интернету"
    if "HTTP Error 404" in text:
        return "Не найдено (404)"
    if "HTTP Error 429" in text:
        return "Слишком много запросов — подождите минуту"
    return text


class Runner(QObject):
    """run(fn, callback, errback): fn in a worker thread, callbacks in the Qt thread."""

    _done = Signal(object, object, object)

    def __init__(self, workers=6):
        super().__init__()
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self._done.connect(self._deliver)

    def run(self, fn, callback=None, errback=None):
        def job():
            try:
                res, err = fn(), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            self._done.emit(callback if err is None else errback, res if err is None else err, None)

        return self.pool.submit(job)

    def _deliver(self, cb, value, _):
        if cb is not None:
            try:
                cb(value)
            except RuntimeError:   # the widget waiting for it is gone
                pass


class IconCache(QObject):
    """Project icons: memory → disk (<data>/cache/icons) → network."""

    def __init__(self, runner):
        super().__init__()
        self.runner = runner
        self.mem = {}
        self.waiting = {}
        self.folder = data_dir() / "cache" / "icons"
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, url):
        ext = Path(urllib.parse.urlparse(url).path).suffix or ".img"
        return self.folder / (hashlib.sha1(url.encode()).hexdigest()[:20] + ext)

    def get(self, url, callback):
        """callback(QPixmap) now (cached) or later; returns the pixmap if it was cached."""
        if not url:
            return None
        if url in self.mem:
            callback(self.mem[url])
            return self.mem[url]
        p = self.path(url)
        if p.exists():
            pix = QPixmap(str(p))
            if not pix.isNull():
                self.mem[url] = pix
                callback(pix)
                return pix
        if url in self.waiting:
            self.waiting[url].append(callback)
            return None
        self.waiting[url] = [callback]

        def fetch():
            data = get_bytes(url, timeout=20)
            p.write_bytes(data)
            return url

        def done(u):
            pix = QPixmap(str(p))
            self.mem[u] = pix
            for cb in self.waiting.pop(u, []):
                try:
                    cb(pix)
                except RuntimeError:
                    pass

        self.runner.run(fetch, done, lambda e: self.waiting.pop(url, None))
        return None
