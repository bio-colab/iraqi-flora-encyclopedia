# -*- coding: utf-8 -*-
"""Quick smoke test against local web_server.py."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from urllib.request import Request

BASE = "http://127.0.0.1:8765"
passed = 0
failed = 0


def get(path: str, headers: dict | None = None):
    req = Request(BASE + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  OK  {name}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        print(f" FAIL {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print("=== Smoke tests ===\n")

    st, ct, body = get("/api/health")
    d = json.loads(body)
    check("GET /api/health", st == 200 and d.get("ok"), f"status={st}")

    st, ct, body = get("/api/stats")
    d = json.loads(body)
    data = d.get("data") or {}
    check(
        "GET /api/stats",
        st == 200 and d.get("ok") and data.get("total") == 152,
        f"total={data.get('total')} native={data.get('native')} families={data.get('families')}",
    )

    st, ct, body = get("/api/enums")
    d = json.loads(body)
    e = d.get("data") or {}
    habits = e.get("habit") or []
    zones = e.get("zones") or []
    check(
        "GET /api/enums",
        st == 200 and bool(habits) and bool(zones),
        f"habits={len(habits)} zones={len(zones)}",
    )

    st, ct, body = get("/api/meta")
    d = json.loads(body)
    check("GET /api/meta", st == 200 and d.get("ok"))

    st, ct, body = get("/api/taxa?limit=5&view=summary")
    d = json.loads(body)
    td = d.get("data") or {}
    results = td.get("results") or []
    check(
        "GET /api/taxa (summary)",
        st == 200 and d.get("ok") and len(results) > 0,
        f"returned={len(results)} total={td.get('total')}",
    )

    st, ct, body = get("/api/taxa?q=%D8%A8%D9%84%D9%88%D8%B7&limit=10&view=summary")
    d = json.loads(body)
    td = d.get("data") or {}
    check(
        "GET /api/taxa search بلوط",
        st == 200 and (td.get("total") or 0) >= 1,
        f"hits={td.get('total')}",
    )

    tid = results[0]["id"] if results else "FAG-QUE-AEG"
    st, ct, body = get(f"/api/taxa/{tid}")
    d = json.loads(body)
    t = d.get("data") or {}
    sci = (t.get("scientific_name") or "")[:40]
    check(f"GET /api/taxa/{tid}", st == 200 and t.get("id") == tid, f"sci={sci}")

    st, ct, body = get("/api/taxa?family=Fagaceae&view=summary&limit=50")
    d = json.loads(body)
    td = d.get("data") or {}
    check(
        "GET /api/taxa family=Fagaceae",
        st == 200 and (td.get("total") or 0) >= 1,
        f"hits={td.get('total')}",
    )

    st, ct, body = get("/api/auth/config")
    d = json.loads(body)
    cfg = d.get("data") or {}
    check(
        "GET /api/auth/config",
        st == 200 and d.get("ok"),
        f"google_configured={cfg.get('google_configured')} dev={cfg.get('allow_dev_login')}",
    )

    st, ct, body = get("/api/auth/me")
    d = json.loads(body)
    perms = (d.get("data") or {}).get("permissions") or {}
    check(
        "GET /api/auth/me (guest)",
        st == 200 and perms.get("can_view") is True and perms.get("can_edit") is not True,
        f"auth={perms.get('is_authenticated')} edit={perms.get('can_edit')}",
    )

    st, ct, body = get("/")
    html = body.decode("utf-8", errors="replace")
    check(
        "GET / (index.html)",
        st == 200 and "statTotal" in html and "موسوعة" in html,
        f"bytes={len(body)} ctype={ct.split(';')[0]}",
    )

    st, ct, body = get("/css/styles.css")
    css = body.decode("utf-8", errors="replace")
    check(
        "GET /css/styles.css",
        st == 200 and ".toast.info" in css and ".modal-backdrop.open" in css,
        f"bytes={len(body)}",
    )

    st, ct, body = get("/js/app.js")
    js = body.decode("utf-8", errors="replace")
    check(
        "GET /js/app.js",
        st == 200 and "updateHeaderStats" in js and "zone-pill" in js,
        f"bytes={len(body)}",
    )

    st, ct, body = get("/js/api.js")
    api_js = body.decode("utf-8", errors="replace")
    check("GET /js/api.js", st == 200 and "listTaxa" in api_js, f"bytes={len(body)}")

    st, ct, body = get("/api/")
    d = json.loads(body)
    check("GET /api/ (docs)", st == 200 and d.get("ok"))

    try:
        get("/api/taxa/DOES-NOT-EXIST-XYZ")
        check("GET missing taxon 404", False, "expected error")
    except urllib.error.HTTPError as err:
        check("GET missing taxon 404", err.code in (404, 400), f"status={err.code}")

    # optional: try dev login if enabled
    try:
        req = Request(
            BASE + "/api/auth/dev-login",
            data=json.dumps(
                {"email": "tester@example.com", "name": "Smoke Tester"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            cookie = r.headers.get("Set-Cookie", "")
            d = json.loads(body)
            check(
                "POST /api/auth/dev-login",
                r.status == 200 and d.get("ok"),
                f"user={(d.get('data') or {}).get('user', {}).get('email', '')}",
            )
            if cookie:
                # session cookie path for me
                # extract first cookie pair
                session_hdr = cookie.split(";")[0]
                st, ct, body = get("/api/auth/me", headers={"Cookie": session_hdr})
                d = json.loads(body)
                user = (d.get("data") or {}).get("user") or {}
                perms = (d.get("data") or {}).get("permissions") or {}
                check(
                    "GET /api/auth/me (after dev-login)",
                    st == 200 and user.get("email") == "tester@example.com",
                    f"role={user.get('role')} can_request={perms.get('can_request_changes')}",
                )
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        check("POST /api/auth/dev-login", False, f"status={err.code} {body[:120]}")
    except Exception as err:  # noqa: BLE001
        check("POST /api/auth/dev-login", False, str(err))

    print(f"\n=== Result: {passed} passed, {failed} failed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
