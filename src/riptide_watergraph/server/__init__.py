"""HTTP server (optional ``[server]`` extra).

Importing this module requires FastAPI; it is loaded on demand by ``riptide serve`` so
the core package stays dependency-light.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
