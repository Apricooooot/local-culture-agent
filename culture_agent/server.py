from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .database import CultureDatabase
from .harness import CultureHarness
from .model import model_from_environment


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


class CultureRequestHandler(BaseHTTPRequestHandler):
    harness: CultureHarness

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json(
                {
                    "ok": True,
                    "model": self.harness.model.name,
                    "entries": len(self.harness.database.list_entries()),
                }
            )
            return
        if path == "/api/library":
            self.send_json({"entries": self.harness.database.list_entries()})
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/chat":
                self.send_json(self.harness.chat(str(payload.get("message", ""))).as_dict())
                return
            if path == "/api/entries":
                self.send_json(self.harness.add_entry(payload), HTTPStatus.CREATED)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/entries/"):
            try:
                entry_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self.send_json({"error": "Invalid entry id"}, HTTPStatus.BAD_REQUEST)
                return
            deleted = self.harness.database.delete_entry(entry_id)
            self.send_json({"deleted": deleted}, HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[culture-agent] {format % args}")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    database_path: str | Path = "data/culture_agent.db",
) -> ThreadingHTTPServer:
    harness = CultureHarness(CultureDatabase(database_path), model_from_environment())
    handler = type("ConfiguredCultureHandler", (CultureRequestHandler,), {"harness": harness})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    host = os.getenv("CULTURE_AGENT_HOST", "127.0.0.1")
    port = int(os.getenv("CULTURE_AGENT_PORT", "8765"))
    server = create_server(host, port)
    print(f"Local Culture Agent is running at http://{host}:{port}")
    print("Your data stays in data/culture_agent.db")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

