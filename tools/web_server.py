# -*- coding: utf-8 -*-
"""
Local HTTP API + static frontend for the Iraqi Flora Encyclopedia.

Stdlib only (no Flask/Django). Serves:
  - REST API under /api/*
  - Google OAuth + role-based access (owner / admin / user / guest)
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
from http.cookies import SimpleCookie
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
from flora_lib.auth import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_OWNER,
    ROLE_USER,
    SESSION_COOKIE,
    AuthError,
    auth_store,
    public_user,
    require_role,
    role_at_least,
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
    server_version = "IraqiFloraAPI/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------------ cookies / user
    def _cookies(self) -> SimpleCookie:
        c = SimpleCookie()
        raw = self.headers.get("Cookie")
        if raw:
            try:
                c.load(raw)
            except Exception:  # noqa: BLE001
                pass
        return c

    def _session_id(self) -> str | None:
        c = self._cookies()
        if SESSION_COOKIE in c:
            return c[SESSION_COOKIE].value
        return None

    def _current_user(self) -> dict | None:
        return auth_store.resolve_session(self._session_id())

    def _base_url(self) -> str:
        host = self.headers.get("Host") or f"{DEFAULT_HOST}:{DEFAULT_PORT}"
        # Prefer http for local stdlib server
        return f"http://{host}"

    def _set_session_cookie_headers(self, sid: str | None, max_age: int | None = None) -> list[str]:
        if sid is None:
            return [
                f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            ]
        age = max_age if max_age is not None else 14 * 86400
        return [
            f"{SESSION_COOKIE}={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}"
        ]

    # ------------------------------------------------------------------ routing
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)

        if path.startswith("/api/"):
            try:
                if path.rstrip("/") == "/api/auth/google/start":
                    self._handle_google_start(qs)
                    return
                if path.rstrip("/") == "/api/auth/google/callback":
                    self._handle_google_callback(qs)
                    return

                result = self._handle_api_get(path, qs)
                if len(result) == 4:
                    status, body, ctype, set_cookies = result
                    self._send(status, body, ctype, set_cookies=set_cookies)
                else:
                    self._send(*result)
            except AuthError as e:
                self._send(*_error(str(e), e.status))
            except Exception as e:  # noqa: BLE001
                self._send(*_error(str(e), 500, trace=traceback.format_exc()))
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
        try:
            result = self._handle_api_post(path, payload, parse_qs(parsed.query))
            if len(result) == 4:
                status, body, ctype, set_cookies = result
                self._send(status, body, ctype, set_cookies=set_cookies)
            else:
                self._send(*result)
        except AuthError as e:
            self._send(*_error(str(e), e.status))
        except (ValidationError, DuplicateError) as e:
            self._send(*_error(str(e), 422))
        except FloraError as e:
            self._send(*_error(str(e), 400))
        except Exception as e:  # noqa: BLE001
            self._send(*_error(str(e), 500, trace=traceback.format_exc()))

    def do_PUT(self) -> None:  # noqa: N802
        self._mutate("put")

    def do_PATCH(self) -> None:  # noqa: N802
        self._mutate("patch")

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        # demote admin
        if path.startswith("/api/auth/admin/users/") and path.endswith("/admin"):
            try:
                user = require_role(self._current_user(), ROLE_OWNER)
                mid = path[len("/api/auth/admin/users/") : -len("/admin")].strip("/")
                email = unquote(mid)
                updated = auth_store.demote_admin(email, actor_email=user["email"])
                self._send(*_ok(public_user(updated), message=f"أُزيلت صلاحية المدير عن {email}"))
            except AuthError as e:
                self._send(*_error(str(e), e.status))
            except Exception as e:  # noqa: BLE001
                self._send(*_error(str(e), 500, trace=traceback.format_exc()))
            return

        if path.startswith("/api/auth/admin/codes/"):
            try:
                user = require_role(self._current_user(), ROLE_OWNER)
                code_id = path[len("/api/auth/admin/codes/") :].strip("/")
                auth_store.revoke_admin_code(code_id, owner_email=user["email"])
                self._send(*_ok(message="أُلغي الكود"))
            except AuthError as e:
                self._send(*_error(str(e), e.status))
            except Exception as e:  # noqa: BLE001
                self._send(*_error(str(e), 500, trace=traceback.format_exc()))
            return

        if not path.startswith("/api/taxa/"):
            self._send(*_error("Not found", 404))
            return
        tid = path[len("/api/taxa/") :].strip("/")
        if not tid or "/" in tid:
            self._send(*_error("معرّف غير صالح", 400))
            return
        try:
            user = require_role(self._current_user(), ROLE_ADMIN)
            m = FloraManager(auto_backup=True)
            removed = m.delete(tid)
            auth_store.log_activity(
                actor_email=user["email"],
                actor_role=user["role"],
                action="taxon.delete",
                target=tid,
                detail={"scientific_name": removed.get("scientific_name")},
            )
            self._send(*_ok(removed, message=f"حُذف {removed['id']}"))
        except AuthError as e:
            self._send(*_error(str(e), e.status))
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
            user = require_role(self._current_user(), ROLE_ADMIN)
            m = FloraManager(auto_backup=True)
            replace = method == "put" or bool(payload.pop("_replace", False))
            updated = m.update(tid, payload, replace=replace)
            auth_store.log_activity(
                actor_email=user["email"],
                actor_role=user["role"],
                action="taxon.update",
                target=updated["id"],
                detail={"scientific_name": updated.get("scientific_name"), "replace": replace},
            )
            self._send(*_ok(updated, message=f"عُدّل {updated['id']}"))
        except AuthError as e:
            self._send(*_error(str(e), e.status))
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
    ) -> tuple[int, bytes, str] | tuple[int, bytes, str, list[str]]:
        # ---- auth routes
        if path in ("/api/auth/config", "/api/auth/config/"):
            return _ok(auth_store.public_config(base_url=self._base_url()))

        if path in ("/api/auth/me", "/api/auth/me/"):
            user = self._current_user()
            return _ok(
                {
                    "user": user,
                    "authenticated": user is not None,
                    "permissions": self._permissions(user),
                }
            )

        if path in ("/api/auth/admin/users", "/api/auth/admin/users/"):
            require_role(self._current_user(), ROLE_OWNER)
            return _ok(auth_store.list_users())

        if path in ("/api/auth/admin/codes", "/api/auth/admin/codes/"):
            require_role(self._current_user(), ROLE_OWNER)
            return _ok(auth_store.list_admin_codes())

        if path in ("/api/auth/activity", "/api/auth/activity/"):
            require_role(self._current_user(), ROLE_ADMIN)
            limit = int(_first(qs, "limit") or 100)
            return _ok(auth_store.list_activity(limit=limit))

        if path in ("/api/requests", "/api/requests/"):
            user = require_role(self._current_user(), ROLE_USER)
            status = _first(qs, "status")
            mine = (_first(qs, "mine") or "").casefold() in ("1", "true", "yes")
            # non-admins always mine-only
            if not role_at_least(user, ROLE_ADMIN):
                mine = True
            return _ok(
                auth_store.list_change_requests(
                    viewer=user, status=status, mine_only=mine
                )
            )

        if path.startswith("/api/requests/"):
            user = require_role(self._current_user(), ROLE_USER)
            rid = path[len("/api/requests/") :].strip("/")
            rec = auth_store.get_change_request(rid)
            if not rec:
                return _error("الطلب غير موجود", 404)
            if not role_at_least(user, ROLE_ADMIN) and rec.get(
                "requester_email"
            ) != user.get("email"):
                return _error("ليست لديك صلاحية عرض هذا الطلب", 403)
            return _ok(rec)

        # ---- public flora API
        try:
            if path in ("/api", "/api/"):
                return _ok(
                    {
                        "name": "Iraqi Flora Encyclopedia API",
                        "schema_version": SCHEMA_VERSION,
                        "auth": True,
                        "endpoints": [
                            "GET /api/health",
                            "GET /api/stats",
                            "GET /api/enums",
                            "GET /api/meta",
                            "GET /api/taxa",
                            "GET /api/taxa/{id}",
                            "POST /api/taxa  (admin+)",
                            "PUT|PATCH /api/taxa/{id}  (admin+)",
                            "DELETE /api/taxa/{id}  (admin+)",
                            "POST /api/suggest-id",
                            "POST /api/search",
                            "GET /api/auth/me",
                            "GET /api/auth/google/start",
                            "POST /api/auth/logout",
                            "POST /api/auth/redeem-code",
                            "GET|POST /api/auth/admin/codes  (owner)",
                            "GET /api/auth/admin/users  (owner)",
                            "GET /api/auth/activity  (admin+)",
                            "GET|POST /api/requests",
                            "POST /api/requests/{id}/approve|reject  (admin+)",
                        ],
                    }
                )

            if path == "/api/health":
                m = FloraManager(auto_backup=False)
                return _ok(
                    {
                        "status": "ok",
                        "taxa": m.count(),
                        "oauth_configured": auth_store.is_oauth_configured(),
                    }
                )

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

    def _handle_google_start(self, qs: dict[str, list[str]]) -> None:
        cfg = auth_store.load_config()
        redirect_uri = (cfg.get("redirect_uri") or "").strip() or (
            f"{self._base_url()}/api/auth/google/callback"
        )
        data = auth_store.begin_google_oauth(redirect_uri=redirect_uri)
        want_json = "application/json" in (self.headers.get("Accept") or "")
        if want_json or _first(qs, "format") == "json":
            self._send(*_ok(data))
            return
        self.send_response(302)
        self.send_header("Location", data["auth_url"])
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _handle_google_callback(self, qs: dict[str, list[str]]) -> None:
        err = _first(qs, "error")
        if err:
            msg = _first(qs, "error_description") or err
            loc = f"/?auth_error={urllib_quote(msg)}"
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()
            return

        code = _first(qs, "code")
        state = _first(qs, "state")
        if not code or not state:
            loc = "/?auth_error=" + urllib_quote("استجابة Google ناقصة")
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()
            return

        try:
            user = auth_store.finish_google_oauth(code=code, state=state)
            sid = auth_store.create_session(user)
            self.send_response(302)
            self.send_header("Location", "/?auth=ok")
            for ch in self._set_session_cookie_headers(sid):
                self.send_header("Set-Cookie", ch)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        except AuthError as e:
            loc = "/?auth_error=" + urllib_quote(str(e))
            self.send_response(302)
            self.send_header("Location", loc)
            self.end_headers()

    def _handle_api_post(
        self,
        path: str,
        payload: Any,
        qs: dict[str, list[str]],
    ) -> tuple[int, bytes, str] | tuple[int, bytes, str, list[str]]:
        # ---- auth
        if path in ("/api/auth/logout", "/api/auth/logout/"):
            user = self._current_user()
            if user:
                auth_store.log_activity(
                    actor_email=user.get("email"),
                    actor_role=user.get("role"),
                    action="auth.logout",
                    target=user.get("email") or "",
                    detail={},
                )
            auth_store.destroy_session(self._session_id())
            status, body, ctype = _ok(message="تم تسجيل الخروج")
            return status, body, ctype, self._set_session_cookie_headers(None)

        if path in ("/api/auth/dev-login", "/api/auth/dev-login/"):
            if not isinstance(payload, dict):
                return _error("جسم JSON مطلوب", 400)
            user = auth_store.dev_login(
                str(payload.get("email") or ""),
                name=str(payload.get("name") or ""),
            )
            sid = auth_store.create_session(user)
            status, body, ctype = _ok(
                {
                    "user": public_user(user),
                    "permissions": self._permissions(public_user(user)),
                },
                message="تم الدخول (وضع التطوير)",
            )
            return status, body, ctype, self._set_session_cookie_headers(sid)

        if path in ("/api/auth/redeem-code", "/api/auth/redeem-code/"):
            user = require_role(self._current_user(), ROLE_USER)
            if not isinstance(payload, dict):
                return _error("جسم JSON مطلوب", 400)
            updated = auth_store.redeem_admin_code(
                str(payload.get("code") or ""),
                user_email=user["email"],
            )
            return _ok(updated, message="أصبحت مديراً")

        if path in ("/api/auth/admin/codes", "/api/auth/admin/codes/"):
            user = require_role(self._current_user(), ROLE_OWNER)
            note = ""
            if isinstance(payload, dict):
                note = str(payload.get("note") or "")
            generated = auth_store.generate_admin_code(
                owner_email=user["email"], note=note
            )
            return _ok(generated, message="تم توليد كود ترقية لمرة واحدة")

        if path in ("/api/requests", "/api/requests/"):
            user = require_role(self._current_user(), ROLE_USER)
            if not isinstance(payload, dict):
                return _error("جسم JSON مطلوب", 400)
            rec = auth_store.create_change_request(
                requester=user,
                req_type=str(payload.get("type") or ""),
                payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else None,
                taxon_id=payload.get("taxon_id"),
                note=str(payload.get("note") or ""),
            )
            return _ok(rec, message="أُرسل الطلب للمراجعة")

        if path.startswith("/api/requests/") and path.endswith("/approve"):
            user = require_role(self._current_user(), ROLE_ADMIN)
            rid = path[len("/api/requests/") : -len("/approve")].strip("/")
            note = ""
            if isinstance(payload, dict):
                note = str(payload.get("note") or payload.get("resolution_note") or "")
            # Load pending request, apply first, then mark approved
            # (avoids approved-but-not-applied if validation fails)
            pending = auth_store.get_change_request(rid)
            if not pending:
                return _error("الطلب غير موجود", 404)
            if pending.get("status") != "pending":
                return _error("الطلب مُعالَج مسبقاً", 400)
            applied = self._apply_approved_request(pending, actor=user)
            rec = auth_store.resolve_change_request(
                rid, resolver=user, approve=True, resolution_note=note
            )
            return _ok({"request": rec, "applied": applied}, message="وُوفق على الطلب وطُبّق")

        if path.startswith("/api/requests/") and path.endswith("/reject"):
            user = require_role(self._current_user(), ROLE_ADMIN)
            rid = path[len("/api/requests/") : -len("/reject")].strip("/")
            note = ""
            if isinstance(payload, dict):
                note = str(payload.get("note") or payload.get("resolution_note") or "")
            rec = auth_store.resolve_change_request(
                rid, resolver=user, approve=False, resolution_note=note
            )
            return _ok(rec, message="رُفض الطلب")

        # ---- flora
        if path == "/api/search":
            if not isinstance(payload, dict):
                payload = {}
            for k, vals in qs.items():
                if vals and k not in payload:
                    payload[k] = vals[0]
            return self._search_from_params(payload)

        if path == "/api/suggest-id":
            if not isinstance(payload, dict):
                return _error("الجسم يجب أن يكون كائن JSON", 400)
            family = str(payload.get("family") or "")
            genus = str(payload.get("genus") or "")
            sci = str(
                payload.get("scientific_name") or payload.get("scientificName") or ""
            )
            if not (family and genus and sci):
                return _error("يلزم family و genus و scientific_name", 400)
            return _ok({"id": suggest_id(family, genus, sci)})

        if path in ("/api/taxa", "/api/taxa/"):
            user = require_role(self._current_user(), ROLE_ADMIN)
            if not isinstance(payload, dict):
                return _error("الجسم يجب أن يكون كائن JSON لصنف واحد", 400)
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
            auth_store.log_activity(
                actor_email=user["email"],
                actor_role=user["role"],
                action="taxon.add",
                target=taxon["id"],
                detail={"scientific_name": taxon.get("scientific_name")},
            )
            return _ok(taxon, message=f"أُضيف {taxon['id']}")

        return _error("Not found", 404)

    def _apply_approved_request(self, rec: dict, *, actor: dict) -> dict | None:
        """Execute flora mutation for an approved change request."""
        m = FloraManager(auto_backup=True)
        rtype = rec.get("type")
        try:
            if rtype == "add":
                body = dict(rec.get("payload") or {})
                if not body.get("id"):
                    cls = body.get("classification") or {}
                    body["id"] = suggest_id(
                        cls.get("family") or "",
                        cls.get("genus") or "",
                        body.get("scientific_name") or "",
                    )
                taxon = m.add(body)
                auth_store.log_activity(
                    actor_email=actor["email"],
                    actor_role=actor["role"],
                    action="taxon.add",
                    target=taxon["id"],
                    detail={
                        "via_request": rec.get("id"),
                        "requester": rec.get("requester_email"),
                    },
                )
                return taxon
            if rtype == "update":
                tid = rec.get("taxon_id") or ""
                body = dict(rec.get("payload") or {})
                updated = m.update(tid, body, replace=True)
                auth_store.log_activity(
                    actor_email=actor["email"],
                    actor_role=actor["role"],
                    action="taxon.update",
                    target=updated["id"],
                    detail={
                        "via_request": rec.get("id"),
                        "requester": rec.get("requester_email"),
                    },
                )
                return updated
            if rtype == "delete":
                tid = rec.get("taxon_id") or ""
                removed = m.delete(tid)
                auth_store.log_activity(
                    actor_email=actor["email"],
                    actor_role=actor["role"],
                    action="taxon.delete",
                    target=tid,
                    detail={
                        "via_request": rec.get("id"),
                        "requester": rec.get("requester_email"),
                    },
                )
                return removed
        except Exception as e:  # noqa: BLE001
            auth_store.log_activity(
                actor_email=actor["email"],
                actor_role=actor["role"],
                action="request.apply_failed",
                target=rec.get("id") or "",
                detail={"error": str(e)},
            )
            raise FloraError(f"وُوفق على الطلب لكن فشل التطبيق: {e}") from e
        return None

    def _permissions(self, user: dict | None) -> dict[str, bool]:
        return {
            "can_view": True,
            "can_request_changes": role_at_least(user, ROLE_USER)
            and not role_at_least(user, ROLE_ADMIN),
            "can_edit": role_at_least(user, ROLE_ADMIN),
            "can_manage_requests": role_at_least(user, ROLE_ADMIN),
            "can_view_activity": role_at_least(user, ROLE_ADMIN),
            "can_manage_admins": role_at_least(user, ROLE_OWNER),
            "can_generate_codes": role_at_least(user, ROLE_OWNER),
            "is_owner": role_at_least(user, ROLE_OWNER),
            "is_admin": role_at_least(user, ROLE_ADMIN),
            "is_authenticated": user is not None,
        }

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
            native=_parse_bool(str(params["native"]))
            if params.get("native") is not None
            else None,
            limit=int(params.get("limit") or 200),
            offset=int(params.get("offset") or 0),
            sort_by=str(params.get("sort_by") or "family"),
            sort_desc=bool(_parse_bool(str(params.get("sort_desc"))))
            if params.get("sort_desc") is not None
            else False,
            endemic=_parse_bool(str(params["endemic"]))
            if params.get("endemic") is not None
            else None,
            flagship=_parse_bool(str(params["flagship"]))
            if params.get("flagship") is not None
            else None,
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
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        )
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Accept, Cookie"
        )
        self.send_header("Access-Control-Allow-Credentials", "true")

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        set_cookies: list[str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.send_header("Cache-Control", "no-store")
        if set_cookies:
            for c in set_cookies:
                self.send_header("Set-Cookie", c)
        self.end_headers()
        if body:
            self.wfile.write(body)


def urllib_quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def run_server(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = True
) -> None:
    if not FRONTEND_DIR.is_dir():
        print(f"تحذير: مجلد الواجهة غير موجود: {FRONTEND_DIR}", file=sys.stderr)

    # ensure auth dir exists
    auth_store.load_config()

    httpd = ThreadingHTTPServer((host, port), FloraAPIHandler)
    url = f"http://{host}:{port}/"
    oauth_ok = auth_store.is_oauth_configured()
    print("=" * 60)
    print("  موسوعة الفلورا العراقية — Iraqi Flora Encyclopedia")
    print(f"  Frontend + API: {url}")
    print(f"  API docs:       {url}api/")
    print(f"  Google OAuth:   {'مُفعّل' if oauth_ok else 'غير مُعدّ (انظر auth_config.example.json)'}")
    print(f"  المالك:         {auth_store.owner_email()}")
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
