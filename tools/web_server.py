# -*- coding: utf-8 -*-
"""
Local HTTP API + static frontend for the Iraqi Flora Encyclopedia.

Stdlib only (no Flask/Django). Serves:
  - REST API under /api/*
  - Frontend assets from frontend/

Usage:
  python tools/web_server.py
  python tools/web_server.py --port 8765 --no-browser
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

# Allow `python tools/web_server.py` without installing package
_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from flora_lib import (  # noqa: E402
    DuplicateError,
    FloraError,
    FloraManager,
    NotFoundError,
    ValidationError,
)
from flora_lib.config import (  # noqa: E402
    ALLOWED_CONFIDENCE,
    ALLOWED_HABIT,
    ALLOWED_LOCAL_STATUS,
    ALLOWED_PRESENCE,
    ALLOWED_ZONES,
    CATEGORY_GROUPS,
    HABIT_FILES,
    IUCN_CODES,
    PROJECT_ROOT,
    SCHEMA_VERSION,
)
from flora_lib.search import summarize_taxon  # noqa: E402
from flora_lib.validate import suggest_id  # noqa: E402

FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _json_bytes(obj: Any, status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def _error(message: str, status: int = 400, **extra: Any) -> tuple[int, bytes, str]:
    payload = {"ok": False, "error": message, **extra}
    return _json_bytes(payload, status)


def _ok(data: Any = None, **extra: Any) -> tuple[int, bytes, str]:
    payload: dict[str, Any] = {"ok": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return _json_bytes(payload, 200)


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None or raw == "":
        return None
    s = raw.strip().casefold()
    if s in ("true", "1", "yes", "y", "نعم"):
        return True
    if s in ("false", "0", "no", "n", "لا"):
        return False
    return None


def _first(qs: dict[str, list[str]], key: str) -> str | None:
    vals = qs.get(key)
    if not vals:
        return None
    v = vals[0].strip()
    return v if v else None


class FloraAPIHandler(BaseHTTPRequestHandler):
    server_version = "IraqiFloraAPI/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------ routing
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path.startswith("/api/"):
            status, body, ctype = self._handle_api_get(path, parse_qs(parsed.query))
            self._send(status, body, ctype)
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not path.startswith("/api/"):
            self._send(*_error("Not found", 404))
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError as e:
            self._send(*_error(f"JSON غير صالح: {e}", 400))
            return
        status, body, ctype = self._handle_api_post(path, payload, parse_qs(parsed.query))
        self._send(status, body, ctype)

    def do_PUT(self) -> None:  # noqa: N802
        self._mutate("put")

    def do_PATCH(self) -> None:  # noqa: N802
        self._mutate("patch")

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not path.startswith("/api/taxa/"):
            self._send(*_error("Not found", 404))
            return
        tid = path[len("/api/taxa/") :].strip("/")
        if not tid or "/" in tid:
            self._send(*_error("معرّف غير صالح", 400))
            return
        try:
            m = FloraManager(auto_backup=True)
            removed = m.delete(tid)
            self._send(*_ok(removed, message=f"حُذف {removed['id']}"))
        except NotFoundError as e:
            self._send(*_error(str(e), 404))
        except FloraError as e:
            self._send(*_error(str(e), 400))
        except Exception as e:  # noqa: BLE001
            self._send(*_error(str(e), 500, trace=traceback.format_exc()))

    def _mutate(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not path.startswith("/api/taxa/"):
            self._send(*_error("Not found", 404))
            return
        tid = path[len("/api/taxa/") :].strip("/")
        if not tid or "/" in tid:
            self._send(*_error("معرّف غير صالح", 400))
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError as e:
            self._send(*_error(f"JSON غير صالح: {e}", 400))
            return
        if not isinstance(payload, dict):
            self._send(*_error("الجسم يجب أن يكون كائن JSON", 400))
            return
        try:
            m = FloraManager(auto_backup=True)
            replace = method == "put" or bool(payload.pop("_replace", False))
            updated = m.update(tid, payload, replace=replace)
            self._send(*_ok(updated, message=f"عُدّل {updated['id']}"))
        except NotFoundError as e:
            self._send(*_error(str(e), 404))
        except (ValidationError, DuplicateError) as e:
            self._send(*_error(str(e), 422))
        except FloraError as e:
            self._send(*_error(str(e), 400))
        except Exception as e:  # noqa: BLE001
            self._send(*_error(str(e), 500, trace=traceback.format_exc()))

    # ------------------------------------------------------------------ API GET
    def _handle_api_get(
        self, path: str, qs: dict[str, list[str]]
    ) -> tuple[int, bytes, str]:
        try:
            if path in ("/api", "/api/"):
                return _ok(
                    {
                        "name": "Iraqi Flora Encyclopedia API",
                        "schema_version": SCHEMA_VERSION,
                        "endpoints": [
                            "GET /api/health",
                            "GET /api/stats",
                            "GET /api/enums",
                            "GET /api/meta",
                            "GET /api/taxa",
                            "GET /api/taxa/{id}",
                            "POST /api/taxa",
                            "PUT|PATCH /api/taxa/{id}",
                            "DELETE /api/taxa/{id}",
                            "POST /api/suggest-id",
                            "POST /api/search",
                        ],
                    }
                )

            if path == "/api/health":
                m = FloraManager(auto_backup=False)
                return _ok({"status": "ok", "taxa": m.count()})

            if path == "/api/stats":
                m = FloraManager(auto_backup=False)
                return _ok(m.stats())

            if path == "/api/enums":
                return _ok(self._enums_payload())

            if path == "/api/meta":
                return _ok(self._meta_payload())

            if path == "/api/taxa":
                return self._list_taxa(qs)

            if path.startswith("/api/taxa/"):
                tid = path[len("/api/taxa/") :].strip("/")
                if not tid or "/" in tid:
                    return _error("معرّف غير صالح", 400)
                m = FloraManager(auto_backup=False)
                return _ok(m.get(tid))

            return _error("Not found", 404)
        except NotFoundError as e:
            return _error(str(e), 404)
        except FloraError as e:
            return _error(str(e), 400)
        except Exception as e:  # noqa: BLE001
            return _error(str(e), 500, trace=traceback.format_exc())

    def _handle_api_post(
        self,
        path: str,
        payload: Any,
        qs: dict[str, list[str]],
    ) -> tuple[int, bytes, str]:
        try:
            if path == "/api/search":
                if not isinstance(payload, dict):
                    payload = {}
                # merge query string over body for convenience
                for k, vals in qs.items():
                    if vals and k not in payload:
                        payload[k] = vals[0]
                return self._search_from_params(payload)

            if path == "/api/suggest-id":
                if not isinstance(payload, dict):
                    return _error("الجسم يجب أن يكون كائن JSON", 400)
                family = str(payload.get("family") or "")
                genus = str(payload.get("genus") or "")
                sci = str(payload.get("scientific_name") or payload.get("scientificName") or "")
                if not (family and genus and sci):
                    return _error("يلزم family و genus و scientific_name", 400)
                return _ok({"id": suggest_id(family, genus, sci)})

            if path in ("/api/taxa", "/api/taxa/"):
                if not isinstance(payload, dict):
                    return _error("الجسم يجب أن يكون كائن JSON لصنف واحد", 400)
                # optional auto id
                if not payload.get("id") and payload.get("_suggest_id"):
                    cls = payload.get("classification") or {}
                    payload["id"] = suggest_id(
                        cls.get("family") or "",
                        cls.get("genus") or "",
                        payload.get("scientific_name") or "",
                    )
                payload.pop("_suggest_id", None)
                m = FloraManager(auto_backup=True)
                taxon = m.add(payload)
                return _ok(taxon, message=f"أُضيف {taxon['id']}")

            return _error("Not found", 404)
        except (ValidationError, DuplicateError) as e:
            return _error(str(e), 422)
        except FloraError as e:
            return _error(str(e), 400)
        except Exception as e:  # noqa: BLE001
            return _error(str(e), 500, trace=traceback.format_exc())

    def _list_taxa(self, qs: dict[str, list[str]]) -> tuple[int, bytes, str]:
        params: dict[str, Any] = {}
        for key in (
            "q",
            "query",
            "text",
            "id",
            "scientific_name",
            "habit",
            "family",
            "genus",
            "order",
            "zone",
            "zones",
            "presence",
            "presence_in_iraq",
            "local_status",
            "iraq_local_status",
            "iucn",
            "category",
            "category_group",
            "sort_by",
            "limit",
            "offset",
        ):
            v = _first(qs, key)
            if v is not None:
                params[key] = v
        for key in ("native", "native_to_iraq", "endemic", "flagship", "sort_desc"):
            v = _first(qs, key)
            if v is not None:
                params[key] = v

        summary = (_first(qs, "view") or _first(qs, "format") or "summary").casefold()
        return self._search_from_params(params, summary=summary != "full")

    def _search_from_params(
        self, params: dict[str, Any], *, summary: bool = True
    ) -> tuple[int, bytes, str]:
        m = FloraManager(auto_backup=False)
        # normalize common aliases
        if "native" not in params and "native_to_iraq" in params:
            params["native"] = params["native_to_iraq"]
        result = m.search_detailed(
            params.get("q") or params.get("query") or params.get("text") or "",
            habit=params.get("habit"),
            family=params.get("family"),
            genus=params.get("genus"),
            zone=params.get("zone") or params.get("zones"),
            presence=params.get("presence") or params.get("presence_in_iraq"),
            local_status=params.get("local_status") or params.get("iraq_local_status"),
            taxon_id=params.get("id"),
            category_group=params.get("category") or params.get("category_group"),
            iucn=params.get("iucn"),
            native=_parse_bool(str(params["native"])) if params.get("native") is not None else None,
            limit=int(params.get("limit") or 200),
            offset=int(params.get("offset") or 0),
            sort_by=str(params.get("sort_by") or "family"),
            sort_desc=bool(_parse_bool(str(params.get("sort_desc")))) if params.get("sort_desc") is not None else False,
            endemic=_parse_bool(str(params["endemic"])) if params.get("endemic") is not None else None,
            flagship=_parse_bool(str(params["flagship"])) if params.get("flagship") is not None else None,
            scientific_name=params.get("scientific_name"),
            order=params.get("order"),
        )
        rows = result["results"]
        if summary:
            rows = [summarize_taxon(t) for t in rows]
        return _ok(
            {
                "total": result["total"],
                "count": result["count"],
                "offset": result["offset"],
                "limit": result["limit"],
                "results": rows,
            }
        )

    def _enums_payload(self) -> dict[str, Any]:
        return {
            "habit": ALLOWED_HABIT,
            "habit_meta": {
                h: {
                    "label_ar": meta["label_ar"],
                    "label_en": meta["label_en"],
                    "category_group": meta["category_group"],
                }
                for h, meta in HABIT_FILES.items()
            },
            "presence_in_iraq": ALLOWED_PRESENCE,
            "iraq_local_status": ALLOWED_LOCAL_STATUS,
            "zones": ALLOWED_ZONES,
            "confidence": ALLOWED_CONFIDENCE,
            "iucn": sorted(IUCN_CODES),
            "category_groups": {
                k: {
                    "habits": v["habits"],
                    "label_ar": v["label_ar"],
                    "label_en": v["label_en"],
                    "file": v["file"],
                }
                for k, v in CATEGORY_GROUPS.items()
            },
            "schema_version": SCHEMA_VERSION,
        }

    def _meta_payload(self) -> dict[str, Any]:
        m = FloraManager(auto_backup=False)
        stats = m.stats()
        index_path = PROJECT_ROOT / "data" / "index.json"
        index = {}
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index = {}
        return {
            "project": "Iraqi Flora Encyclopedia",
            "project_ar": "موسوعة الفلورا العراقية",
            "schema_version": SCHEMA_VERSION,
            "stats": stats,
            "index": index.get("totals") or {},
            "author": "Elias Sharar / bio-colab",
        }

    # ------------------------------------------------------------------ static
    def _serve_static(self, path: str) -> None:
        if path in ("", "/"):
            rel = "index.html"
        else:
            rel = path.lstrip("/").replace("\\", "/")
            if ".." in rel.split("/"):
                self._send(*_error("Forbidden", 403))
                return

        file_path = (FRONTEND_DIR / rel).resolve()
        try:
            file_path.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send(*_error("Forbidden", 403))
            return

        if file_path.is_dir():
            file_path = file_path / "index.html"

        if not file_path.is_file():
            # SPA fallback
            index = FRONTEND_DIR / "index.html"
            if index.is_file() and not rel.startswith("api"):
                file_path = index
            else:
                self._send(*_error("Not found", 404))
                return

        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in (
            "application/javascript",
            "application/json",
            "image/svg+xml",
        ):
            ctype = f"{ctype}; charset=utf-8"
        self._send(200, data, ctype)

    # ------------------------------------------------------------------ IO
    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    if not FRONTEND_DIR.is_dir():
        print(f"تحذير: مجلد الواجهة غير موجود: {FRONTEND_DIR}", file=sys.stderr)

    httpd = ThreadingHTTPServer((host, port), FloraAPIHandler)
    url = f"http://{host}:{port}/"
    print("=" * 60)
    print("  موسوعة الفلورا العراقية — Iraqi Flora Encyclopedia")
    print(f"  Frontend + API: {url}")
    print(f"  API docs:       {url}api/")
    print("  اضغط Ctrl+C للإيقاف")
    print("=" * 60)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nإيقاف الخادم…")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Iraqi Flora web UI + API server")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args(argv)
    run_server(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
