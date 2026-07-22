# -*- coding: utf-8 -*-
"""
Authentication, roles, admin codes, change requests, and activity log.

Roles:
  - owner  — fixed email (aliasbio95@gmail.com)
  - admin  — promoted via one-time owner-issued codes
  - user   — signed-in via Google (can submit change requests)
  - guest  — not signed in (read-only)

Storage (JSON under data/auth/):
  config.json, users.json, sessions.json, admin_codes.json,
  change_requests.json, activity.jsonl, secret.key
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, PROJECT_ROOT

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OWNER_EMAIL = "aliasbio95@gmail.com"

AUTH_DIR = DATA_DIR / "auth"
CONFIG_PATH = AUTH_DIR / "config.json"
USERS_PATH = AUTH_DIR / "users.json"
SESSIONS_PATH = AUTH_DIR / "sessions.json"
CODES_PATH = AUTH_DIR / "admin_codes.json"
REQUESTS_PATH = AUTH_DIR / "change_requests.json"
ACTIVITY_PATH = AUTH_DIR / "activity.jsonl"
SECRET_PATH = AUTH_DIR / "secret.key"

# Also accept env-based / project-root config
ROOT_CONFIG_PATH = PROJECT_ROOT / "auth_config.json"

SESSION_COOKIE = "flora_sid"
SESSION_DAYS = 14
CODE_TTL_HOURS = 48
CODE_LENGTH = 10
OAUTH_STATE_TTL_SEC = 600

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_GUEST = "guest"

ROLE_RANK = {
    ROLE_GUEST: 0,
    ROLE_USER: 1,
    ROLE_ADMIN: 2,
    ROLE_OWNER: 3,
}

_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _utc_ts() -> float:
    return time.time()


def _ensure_auth_dir() -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return deepcopy(default)


def _write_json(path: Path, obj: Any) -> None:
    _ensure_auth_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def _norm_email(email: str | None) -> str:
    return (email or "").strip().casefold()


def public_user(user: dict | None) -> dict | None:
    """Safe user payload for the client (no internal secrets)."""
    if not user:
        return None
    return {
        "email": user.get("email"),
        "name": user.get("name") or "",
        "picture": user.get("picture") or "",
        "role": user.get("role") or ROLE_USER,
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


# ---------------------------------------------------------------------------
# AuthStore
# ---------------------------------------------------------------------------


class AuthError(Exception):
    """Auth / authorization failure."""

    def __init__(self, message: str, status: int = 401) -> None:
        super().__init__(message)
        self.status = status


class AuthStore:
    """Thread-safe auth persistence and Google OAuth helpers."""

    def __init__(self) -> None:
        _ensure_auth_dir()
        self._secret = self._load_or_create_secret()
        # short-lived OAuth state → {created, code_verifier, nonce}
        self._oauth_states: dict[str, dict[str, Any]] = {}

    # ---- secret / config -------------------------------------------------

    def _load_or_create_secret(self) -> bytes:
        if SECRET_PATH.exists():
            raw = SECRET_PATH.read_bytes().strip()
            if raw:
                return raw
        secret = secrets.token_bytes(32)
        SECRET_PATH.write_bytes(secret)
        try:
            os.chmod(SECRET_PATH, 0o600)
        except OSError:
            pass
        return secret

    def load_config(self) -> dict[str, Any]:
        """
        Merge config from (priority high→low):
          env vars, auth_config.json (root), data/auth/config.json
        """
        cfg: dict[str, Any] = {
            "google_client_id": "",
            "google_client_secret": "",
            "owner_email": OWNER_EMAIL,
            "redirect_uri": "",
            "allow_dev_login": False,
        }
        file_cfg = _read_json(CONFIG_PATH, {})
        if isinstance(file_cfg, dict):
            cfg.update({k: v for k, v in file_cfg.items() if v is not None})
        root_cfg = _read_json(ROOT_CONFIG_PATH, {})
        if isinstance(root_cfg, dict):
            cfg.update({k: v for k, v in root_cfg.items() if v is not None})

        env_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        env_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        env_redirect = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
        if env_id:
            cfg["google_client_id"] = env_id
        if env_secret:
            cfg["google_client_secret"] = env_secret
        if env_redirect:
            cfg["redirect_uri"] = env_redirect

        cfg["owner_email"] = _norm_email(cfg.get("owner_email") or OWNER_EMAIL)
        cfg["allow_dev_login"] = bool(cfg.get("allow_dev_login"))
        return cfg

    def is_oauth_configured(self) -> bool:
        cfg = self.load_config()
        return bool(cfg.get("google_client_id") and cfg.get("google_client_secret"))

    def owner_email(self) -> str:
        return _norm_email(self.load_config().get("owner_email") or OWNER_EMAIL)

    def public_config(self, *, base_url: str = "") -> dict[str, Any]:
        cfg = self.load_config()
        return {
            "oauth_configured": self.is_oauth_configured(),
            "allow_dev_login": bool(cfg.get("allow_dev_login")),
            "owner_email": self.owner_email(),
            "google_client_id": cfg.get("google_client_id") or "",
            "redirect_uri": cfg.get("redirect_uri")
            or (f"{base_url.rstrip('/')}/api/auth/google/callback" if base_url else ""),
            "session_cookie": SESSION_COOKIE,
        }

    # ---- users -----------------------------------------------------------

    def _load_users(self) -> dict[str, dict]:
        data = _read_json(USERS_PATH, {"users": {}})
        users = data.get("users") if isinstance(data, dict) else {}
        return users if isinstance(users, dict) else {}

    def _save_users(self, users: dict[str, dict]) -> None:
        _write_json(USERS_PATH, {"users": users, "updated_at": _now_iso()})

    def get_user(self, email: str) -> dict | None:
        key = _norm_email(email)
        with _lock:
            users = self._load_users()
            u = users.get(key)
            return deepcopy(u) if u else None

    def list_users(self) -> list[dict]:
        with _lock:
            users = self._load_users()
            rows = [public_user(u) for u in users.values()]
            rows = [r for r in rows if r]
            rows.sort(key=lambda r: (ROLE_RANK.get(r["role"], 0) * -1, r["email"] or ""))
            return rows

    def upsert_google_user(
        self,
        *,
        email: str,
        name: str = "",
        picture: str = "",
        google_sub: str = "",
    ) -> dict:
        key = _norm_email(email)
        if not key or "@" not in key:
            raise AuthError("بريد Google غير صالح", 400)
        with _lock:
            users = self._load_users()
            existing = users.get(key)
            role = ROLE_OWNER if key == self.owner_email() else ROLE_USER
            if existing:
                # preserve elevated roles; force owner for owner email
                if key == self.owner_email():
                    role = ROLE_OWNER
                else:
                    role = existing.get("role") or ROLE_USER
                    if role == ROLE_OWNER and key != self.owner_email():
                        role = ROLE_USER
                user = {
                    **existing,
                    "email": key,
                    "name": name or existing.get("name") or "",
                    "picture": picture or existing.get("picture") or "",
                    "google_sub": google_sub or existing.get("google_sub") or "",
                    "role": role,
                    "last_login_at": _now_iso(),
                }
            else:
                user = {
                    "email": key,
                    "name": name or "",
                    "picture": picture or "",
                    "google_sub": google_sub or "",
                    "role": role,
                    "created_at": _now_iso(),
                    "last_login_at": _now_iso(),
                    "promoted_at": None,
                    "promoted_by": None,
                }
            users[key] = user
            self._save_users(users)
            return deepcopy(user)

    def set_role(
        self,
        email: str,
        role: str,
        *,
        actor_email: str | None = None,
    ) -> dict:
        key = _norm_email(email)
        if role not in (ROLE_USER, ROLE_ADMIN, ROLE_OWNER):
            raise AuthError("دور غير صالح", 400)
        if key == self.owner_email() and role != ROLE_OWNER:
            raise AuthError("لا يمكن تغيير دور المالك", 400)
        if role == ROLE_OWNER and key != self.owner_email():
            raise AuthError("المالك حساب واحد ثابت", 400)
        with _lock:
            users = self._load_users()
            if key not in users:
                raise AuthError("المستخدم غير موجود", 404)
            users[key]["role"] = role
            if role == ROLE_ADMIN:
                users[key]["promoted_at"] = _now_iso()
                users[key]["promoted_by"] = actor_email
            elif role == ROLE_USER:
                users[key]["promoted_at"] = None
                users[key]["promoted_by"] = None
            self._save_users(users)
            return deepcopy(users[key])

    def demote_admin(self, email: str, *, actor_email: str) -> dict:
        key = _norm_email(email)
        if key == self.owner_email():
            raise AuthError("لا يمكن إزالة المالك", 400)
        user = self.get_user(key)
        if not user:
            raise AuthError("المستخدم غير موجود", 404)
        if user.get("role") != ROLE_ADMIN:
            raise AuthError("المستخدم ليس مديراً", 400)
        updated = self.set_role(key, ROLE_USER, actor_email=actor_email)
        self.log_activity(
            actor_email=actor_email,
            actor_role=ROLE_OWNER,
            action="admin.demote",
            target=key,
            detail={"from": ROLE_ADMIN, "to": ROLE_USER},
        )
        return updated

    # ---- sessions --------------------------------------------------------

    def _load_sessions(self) -> dict[str, dict]:
        data = _read_json(SESSIONS_PATH, {"sessions": {}})
        sessions = data.get("sessions") if isinstance(data, dict) else {}
        return sessions if isinstance(sessions, dict) else {}

    def _save_sessions(self, sessions: dict[str, dict]) -> None:
        # prune expired
        now = _utc_ts()
        live = {k: v for k, v in sessions.items() if float(v.get("expires_at", 0)) > now}
        _write_json(SESSIONS_PATH, {"sessions": live, "updated_at": _now_iso()})

    def create_session(self, user: dict) -> str:
        sid = secrets.token_urlsafe(32)
        expires = _utc_ts() + SESSION_DAYS * 86400
        with _lock:
            sessions = self._load_sessions()
            sessions[sid] = {
                "email": _norm_email(user.get("email")),
                "created_at": _now_iso(),
                "expires_at": expires,
            }
            self._save_sessions(sessions)
        return sid

    def destroy_session(self, sid: str | None) -> None:
        if not sid:
            return
        with _lock:
            sessions = self._load_sessions()
            if sid in sessions:
                del sessions[sid]
                self._save_sessions(sessions)

    def resolve_session(self, sid: str | None) -> dict | None:
        """Return public user for a valid session cookie value."""
        if not sid:
            return None
        with _lock:
            sessions = self._load_sessions()
            rec = sessions.get(sid)
            if not rec:
                return None
            if float(rec.get("expires_at", 0)) <= _utc_ts():
                del sessions[sid]
                self._save_sessions(sessions)
                return None
            email = rec.get("email")
            user = self._load_users().get(_norm_email(email))
            if not user:
                return None
            # live role fix for owner
            if _norm_email(user.get("email")) == self.owner_email():
                if user.get("role") != ROLE_OWNER:
                    user["role"] = ROLE_OWNER
                    users = self._load_users()
                    users[_norm_email(user["email"])] = user
                    self._save_users(users)
            return public_user(user)

    # ---- Google OAuth ----------------------------------------------------

    def _pkce_pair(self) -> tuple[str, str]:
        verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    def begin_google_oauth(self, *, redirect_uri: str) -> dict[str, str]:
        cfg = self.load_config()
        client_id = (cfg.get("google_client_id") or "").strip()
        if not client_id:
            raise AuthError(
                "تسجيل Google غير مُعدّ. ضع google_client_id و google_client_secret "
                "في auth_config.json أو متغيرات البيئة.",
                503,
            )
        state = secrets.token_urlsafe(24)
        verifier, challenge = self._pkce_pair()
        nonce = secrets.token_urlsafe(16)
        with _lock:
            # purge old states
            cutoff = _utc_ts() - OAUTH_STATE_TTL_SEC
            self._oauth_states = {
                k: v for k, v in self._oauth_states.items() if v.get("ts", 0) >= cutoff
            }
            self._oauth_states[state] = {
                "ts": _utc_ts(),
                "code_verifier": verifier,
                "nonce": nonce,
                "redirect_uri": redirect_uri,
            }
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
        url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)
        return {"auth_url": url, "state": state}

    def finish_google_oauth(self, *, code: str, state: str) -> dict:
        with _lock:
            st = self._oauth_states.pop(state, None)
        if not st or float(st.get("ts", 0)) < _utc_ts() - OAUTH_STATE_TTL_SEC:
            raise AuthError("جلسة OAuth منتهية أو غير صالحة. أعد المحاولة.", 400)

        cfg = self.load_config()
        client_id = (cfg.get("google_client_id") or "").strip()
        client_secret = (cfg.get("google_client_secret") or "").strip()
        redirect_uri = st.get("redirect_uri") or cfg.get("redirect_uri")
        if not client_id or not client_secret:
            raise AuthError("إعدادات Google ناقصة", 503)

        token_body = urllib.parse.urlencode(
            {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": st["code_verifier"],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            GOOGLE_TOKEN_URL,
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                token_payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:400]
            raise AuthError(f"فشل تبادل رمز Google: {detail}", 400) from e
        except urllib.error.URLError as e:
            raise AuthError(f"تعذّر الاتصال بـ Google: {e}", 502) from e

        access_token = token_payload.get("access_token")
        if not access_token:
            raise AuthError("لم يُرجع Google رمز وصول", 400)

        info_req = urllib.request.Request(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(info_req, timeout=15) as resp:
                info = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise AuthError("فشل جلب ملف المستخدم من Google", 400) from e

        email = _norm_email(info.get("email"))
        if not email:
            raise AuthError("حساب Google بلا بريد إلكتروني", 400)
        if info.get("email_verified") is False:
            raise AuthError("البريد غير موثّق لدى Google", 400)

        user = self.upsert_google_user(
            email=email,
            name=str(info.get("name") or ""),
            picture=str(info.get("picture") or ""),
            google_sub=str(info.get("sub") or ""),
        )
        self.log_activity(
            actor_email=email,
            actor_role=user.get("role") or ROLE_USER,
            action="auth.login",
            target=email,
            detail={"provider": "google"},
        )
        return user

    def dev_login(self, email: str, name: str = "") -> dict:
        """Local-only login when allow_dev_login is true (no Google)."""
        cfg = self.load_config()
        if not cfg.get("allow_dev_login"):
            raise AuthError("تسجيل التطوير معطّل", 403)
        email = _norm_email(email)
        if not email or "@" not in email:
            raise AuthError("بريد غير صالح", 400)
        user = self.upsert_google_user(
            email=email,
            name=name or email.split("@")[0],
            picture="",
            google_sub=f"dev:{email}",
        )
        self.log_activity(
            actor_email=email,
            actor_role=user.get("role") or ROLE_USER,
            action="auth.login",
            target=email,
            detail={"provider": "dev"},
        )
        return user

    # ---- admin promotion codes -------------------------------------------

    def _load_codes(self) -> list[dict]:
        data = _read_json(CODES_PATH, {"codes": []})
        codes = data.get("codes") if isinstance(data, dict) else []
        return codes if isinstance(codes, list) else []

    def _save_codes(self, codes: list[dict]) -> None:
        _write_json(CODES_PATH, {"codes": codes, "updated_at": _now_iso()})

    def _hash_code(self, raw: str) -> str:
        return hmac.new(self._secret, raw.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_admin_code(self, *, owner_email: str, note: str = "") -> dict:
        if _norm_email(owner_email) != self.owner_email():
            raise AuthError("توليد أكواد الترقية للمالك فقط", 403)
        raw = secrets.token_hex(CODE_LENGTH // 2).upper()
        # format XXXX-XXXX-XX style for readability
        pretty = f"{raw[0:4]}-{raw[4:8]}-{raw[8:10]}" if len(raw) >= 10 else raw
        code_hash = self._hash_code(pretty.replace("-", "").casefold())
        rec = {
            "id": secrets.token_hex(8),
            "code_hash": code_hash,
            "code_hint": pretty[:4] + "-****-**",
            "created_at": _now_iso(),
            "created_by": self.owner_email(),
            "expires_at": _utc_ts() + CODE_TTL_HOURS * 3600,
            "used_at": None,
            "used_by": None,
            "note": (note or "").strip()[:200],
            "revoked": False,
        }
        with _lock:
            codes = self._load_codes()
            codes.insert(0, rec)
            # keep last 100
            codes = codes[:100]
            self._save_codes(codes)
        self.log_activity(
            actor_email=owner_email,
            actor_role=ROLE_OWNER,
            action="admin.code_generate",
            target=rec["id"],
            detail={"hint": rec["code_hint"], "note": rec["note"]},
        )
        # return plaintext once
        return {
            "id": rec["id"],
            "code": pretty,
            "expires_at": rec["expires_at"],
            "expires_in_hours": CODE_TTL_HOURS,
            "note": rec["note"],
            "hint": rec["code_hint"],
        }

    def list_admin_codes(self) -> list[dict]:
        with _lock:
            codes = self._load_codes()
        now = _utc_ts()
        out = []
        for c in codes:
            out.append(
                {
                    "id": c.get("id"),
                    "hint": c.get("code_hint"),
                    "created_at": c.get("created_at"),
                    "expires_at": c.get("expires_at"),
                    "expired": float(c.get("expires_at") or 0) < now,
                    "used_at": c.get("used_at"),
                    "used_by": c.get("used_by"),
                    "note": c.get("note") or "",
                    "revoked": bool(c.get("revoked")),
                    "status": (
                        "revoked"
                        if c.get("revoked")
                        else "used"
                        if c.get("used_at")
                        else "expired"
                        if float(c.get("expires_at") or 0) < now
                        else "active"
                    ),
                }
            )
        return out

    def revoke_admin_code(self, code_id: str, *, owner_email: str) -> None:
        if _norm_email(owner_email) != self.owner_email():
            raise AuthError("للمالك فقط", 403)
        with _lock:
            codes = self._load_codes()
            found = False
            for c in codes:
                if c.get("id") == code_id:
                    c["revoked"] = True
                    found = True
                    break
            if not found:
                raise AuthError("الكود غير موجود", 404)
            self._save_codes(codes)
        self.log_activity(
            actor_email=owner_email,
            actor_role=ROLE_OWNER,
            action="admin.code_revoke",
            target=code_id,
            detail={},
        )

    def redeem_admin_code(self, raw_code: str, *, user_email: str) -> dict:
        email = _norm_email(user_email)
        user = self.get_user(email)
        if not user:
            raise AuthError("يجب تسجيل الدخول أولاً", 401)
        if user.get("role") in (ROLE_ADMIN, ROLE_OWNER):
            raise AuthError("حسابك مدير بالفعل", 400)

        cleaned = (raw_code or "").strip().replace(" ", "").replace("-", "").casefold()
        if len(cleaned) < 8:
            raise AuthError("كود غير صالح", 400)
        # re-pretty for hash consistency with generated format
        # we hash the pretty form without dashes casefold of full token
        # generate used: pretty without dashes casefold of hex upper
        # Store hash of pretty.replace("-","").casefold() which is hex.casefold()
        code_hash = self._hash_code(cleaned)

        with _lock:
            codes = self._load_codes()
            match = None
            for c in codes:
                if c.get("code_hash") == code_hash:
                    match = c
                    break
            if not match:
                raise AuthError("الكود غير صحيح", 400)
            if match.get("revoked"):
                raise AuthError("الكود مُلغى", 400)
            if match.get("used_at"):
                raise AuthError("الكود مُستخدم مسبقاً", 400)
            if float(match.get("expires_at") or 0) < _utc_ts():
                raise AuthError("الكود منتهٍ الصلاحية", 400)

            match["used_at"] = _now_iso()
            match["used_by"] = email
            self._save_codes(codes)

        updated = self.set_role(email, ROLE_ADMIN, actor_email=self.owner_email())
        self.log_activity(
            actor_email=email,
            actor_role=ROLE_ADMIN,
            action="admin.promote",
            target=email,
            detail={"code_id": match.get("id")},
        )
        return public_user(updated)  # type: ignore[return-value]

    # ---- change requests -------------------------------------------------

    def _load_requests(self) -> list[dict]:
        data = _read_json(REQUESTS_PATH, {"requests": []})
        reqs = data.get("requests") if isinstance(data, dict) else []
        return reqs if isinstance(reqs, list) else []

    def _save_requests(self, reqs: list[dict]) -> None:
        _write_json(REQUESTS_PATH, {"requests": reqs, "updated_at": _now_iso()})

    def create_change_request(
        self,
        *,
        requester: dict,
        req_type: str,
        payload: dict | None = None,
        taxon_id: str | None = None,
        note: str = "",
    ) -> dict:
        role = requester.get("role") or ROLE_USER
        if ROLE_RANK.get(role, 0) < ROLE_RANK[ROLE_USER]:
            raise AuthError("يلزم تسجيل الدخول لطلب تعديل", 401)
        if role in (ROLE_ADMIN, ROLE_OWNER):
            raise AuthError("المديرون يعدّلون مباشرة دون طلب", 400)

        req_type = (req_type or "").strip().casefold()
        if req_type not in ("add", "update", "delete"):
            raise AuthError("نوع الطلب: add | update | delete", 400)

        if req_type in ("update", "delete") and not (taxon_id or "").strip():
            raise AuthError("يلزم taxon_id لطلب التعديل/الحذف", 400)
        if req_type in ("add", "update") and not isinstance(payload, dict):
            raise AuthError("يلزم payload (كائن الصنف) للإضافة/التعديل", 400)

        rec = {
            "id": "req_" + secrets.token_hex(8),
            "type": req_type,
            "status": "pending",
            "requester_email": _norm_email(requester.get("email")),
            "requester_name": requester.get("name") or "",
            "taxon_id": (taxon_id or "").strip().upper() or None,
            "payload": payload if isinstance(payload, dict) else None,
            "note": (note or "").strip()[:1000],
            "created_at": _now_iso(),
            "resolved_at": None,
            "resolved_by": None,
            "resolution_note": None,
        }
        with _lock:
            reqs = self._load_requests()
            reqs.insert(0, rec)
            self._save_requests(reqs[:500])
        self.log_activity(
            actor_email=rec["requester_email"],
            actor_role=ROLE_USER,
            action=f"request.create.{req_type}",
            target=rec["id"],
            detail={"taxon_id": rec["taxon_id"]},
        )
        return deepcopy(rec)

    def list_change_requests(
        self,
        *,
        viewer: dict | None,
        status: str | None = None,
        mine_only: bool = False,
    ) -> list[dict]:
        if not viewer:
            raise AuthError("يلزم تسجيل الدخول", 401)
        with _lock:
            reqs = self._load_requests()
        role = viewer.get("role") or ROLE_USER
        email = _norm_email(viewer.get("email"))
        out = []
        for r in reqs:
            if status and r.get("status") != status:
                continue
            if mine_only or role not in (ROLE_ADMIN, ROLE_OWNER):
                if r.get("requester_email") != email:
                    continue
            out.append(deepcopy(r))
        return out

    def get_change_request(self, req_id: str) -> dict | None:
        with _lock:
            for r in self._load_requests():
                if r.get("id") == req_id:
                    return deepcopy(r)
        return None

    def resolve_change_request(
        self,
        req_id: str,
        *,
        resolver: dict,
        approve: bool,
        resolution_note: str = "",
    ) -> dict:
        role = resolver.get("role") or ROLE_USER
        if role not in (ROLE_ADMIN, ROLE_OWNER):
            raise AuthError("مراجعة الطلبات للمديرين فقط", 403)
        with _lock:
            reqs = self._load_requests()
            idx = next((i for i, r in enumerate(reqs) if r.get("id") == req_id), None)
            if idx is None:
                raise AuthError("الطلب غير موجود", 404)
            rec = reqs[idx]
            if rec.get("status") != "pending":
                raise AuthError("الطلب مُعالَج مسبقاً", 400)
            rec["status"] = "approved" if approve else "rejected"
            rec["resolved_at"] = _now_iso()
            rec["resolved_by"] = _norm_email(resolver.get("email"))
            rec["resolution_note"] = (resolution_note or "").strip()[:1000]
            reqs[idx] = rec
            self._save_requests(reqs)
            result = deepcopy(rec)
        self.log_activity(
            actor_email=result["resolved_by"],
            actor_role=role,
            action="request.approve" if approve else "request.reject",
            target=req_id,
            detail={
                "type": result.get("type"),
                "taxon_id": result.get("taxon_id"),
                "requester": result.get("requester_email"),
            },
        )
        return result

    # ---- activity log ----------------------------------------------------

    def log_activity(
        self,
        *,
        actor_email: str | None,
        actor_role: str | None,
        action: str,
        target: str = "",
        detail: dict | None = None,
    ) -> None:
        _ensure_auth_dir()
        entry = {
            "ts": _now_iso(),
            "actor_email": _norm_email(actor_email) if actor_email else None,
            "actor_role": actor_role,
            "action": action,
            "target": target,
            "detail": detail or {},
        }
        with _lock:
            with ACTIVITY_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list_activity(self, *, limit: int = 100) -> list[dict]:
        if not ACTIVITY_PATH.exists():
            return []
        limit = max(1, min(int(limit or 100), 500))
        with _lock:
            lines = ACTIVITY_PATH.read_text(encoding="utf-8").splitlines()
        rows: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= limit:
                break
        return rows


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------


def role_at_least(user: dict | None, min_role: str) -> bool:
    if not user:
        return min_role == ROLE_GUEST
    return ROLE_RANK.get(user.get("role") or ROLE_GUEST, 0) >= ROLE_RANK.get(min_role, 0)


def require_role(user: dict | None, min_role: str) -> dict:
    if not role_at_least(user, min_role):
        if not user:
            raise AuthError("يلزم تسجيل الدخول", 401)
        raise AuthError("ليست لديك صلاحية لهذا الإجراء", 403)
    return user  # type: ignore[return-value]


# Singleton used by the web server
auth_store = AuthStore()
