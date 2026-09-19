"""
textutil.py — Windows-safe UTF-8 console output.

Call once at every entry point that prints Persian text.
"""
import io, os, sys

_APPLIED = False

def enable_utf8_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows; no-op elsewhere."""
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        buf = getattr(stream, "buffer", None)
        if buf is None:
            continue
        enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if enc == "utf8":
            continue
        try:
            setattr(sys, name,
                    io.TextIOWrapper(buf, encoding="utf-8",
                                     errors="replace", line_buffering=True))
        except Exception:
            pass
