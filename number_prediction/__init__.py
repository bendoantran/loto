"""Isolated, past-only lottery probability experiments."""
__version__ = "0.1.0"


def configure_cli():
    """Keep Vietnamese labels readable in redirected Windows CLI output."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
