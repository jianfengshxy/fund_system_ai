import mimetypes
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


DIST_DIR = Path(__file__).resolve().parent / "dist"
PORT = int(os.environ.get("PORT", "9000"))


class SpaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def _rewrite_path(self):
        parsed = urlparse(self.path)
        request_path = unquote(parsed.path.lstrip("/"))
        candidate = DIST_DIR / request_path

        if parsed.path in ("", "/"):
            self.path = "/index.html"
        elif candidate.is_file():
            self.path = parsed.path
        elif "." not in Path(request_path).name:
            self.path = "/index.html"
        else:
            self.path = parsed.path

        self._resolved_path = self.path

    def do_GET(self):
        self._rewrite_path()
        return super().do_GET()

    def do_HEAD(self):
        self._rewrite_path()
        return super().do_HEAD()

    def end_headers(self):
        resolved = getattr(self, "_resolved_path", self.path)
        if resolved.endswith(".html"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        else:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        super().end_headers()


if __name__ == "__main__":
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SpaHandler)
    print(f"Serving frontend dist from {DIST_DIR} on port {PORT}", flush=True)
    server.serve_forever()
