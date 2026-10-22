"""Discord Rich Presence for Eta."""
import threading

try:
    from pypresence import Presence
    _available = True
except ImportError:
    _available = False

CLIENT_ID = "1562885493018988664"
_rpc = None
_lock = threading.Lock()


def _connect():
    global _rpc
    try:
        rpc = Presence(CLIENT_ID)
        rpc.connect()
        _rpc = rpc
    except Exception:
        _rpc = None


def start():
    """Connect to Discord in background. Safe to call if Discord is not running."""
    if not _available:
        return
    t = threading.Thread(target=_connect, daemon=True)
    t.start()


def update(state=None, details=None, start_ts=None):
    """Update presence. details = instance name, state = activity."""
    if not _available or _rpc is None:
        return
    with _lock:
        try:
            _rpc.update(
                large_image="eta",
                large_text="Эта — Minecraft Launcher",
                details=details,
                state=state,
                start=start_ts,
            )
        except Exception:
            pass


def clear():
    """Clear presence (e.g. when game exits)."""
    if not _available or _rpc is None:
        return
    with _lock:
        try:
            _rpc.clear()
        except Exception:
            pass


def stop():
    global _rpc
    if _rpc is not None:
        with _lock:
            try:
                _rpc.close()
            except Exception:
                pass
            _rpc = None
