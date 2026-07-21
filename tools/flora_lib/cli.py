# -*- coding: utf-8 -*-
"""
Command-line interface for Iraqi Flora management.

Examples:
  python tools/manage_flora.py stats
  python tools/manage_flora.py list --habit شجرة
  python tools/manage_flora.py get FAG-QUE-AEG
  python tools/manage_flora.py search بلوط
  python tools/manage_flora.py add --file taxon.json
  python tools/manage_flora.py update FAG-QUE-AEG --set "iraq_local_status=متراجع"
  python tools/manage_flora.py delete DEMO-XXX-001 --yes
  python tools/manage_flora.py rebuild
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow `python tools/manage_flora.py` without installing package
_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from flora_lib.config import (  # noqa: E402
    ALLOWED_HABIT,
    ALLOWED_LOCAL_STATUS,
    ALLOWED_PRESENCE,
    ALLOWED_ZONES,
    PROJECT_ROOT,
)
from flora_lib.errors import DuplicateError, FloraError, NotFoundError, ValidationError  # noqa: E402
from flora_lib.manager import FloraManager  # noqa: E402
from flora_lib.validate import suggest_id  # noqa: E402


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _parse_set_args(items: list[str] | None) -> dict:
    """Parse --set key=value (supports dotted keys and JSON values)."""
    patch: dict = {}
    if not items:
        return patch
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--set يتوقع key=value، حصلت على: {item!r}")
        key, raw_val = item.split("=", 1)
        key = key.strip()
        raw_val = raw_val.strip()
        try:
            value: Any = json.loads(raw_val)
        except json.JSONDecodeError:
            # booleans / null in plain form
            low = raw_val.casefold()
            if low in ("true", "yes", "1"):
                value = True
            elif low in ("false", "no", "0"):
                value = False
            elif low in ("null", "none"):
                value = None
            else:
                value = raw_val

        # dotted path
        parts = key.split(".")
        cursor = patch
        for p in parts[:-1]:
            cursor = cursor.setdefault(p, {})
            if not isinstance(cursor, dict):
                raise SystemExit(f"مسار --set غير صالح: {key}")
        cursor[parts[-1]] = value
    return patch


def cmd_stats(_: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    _print_json(m.stats())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    rows = m.list_summaries(
        habit=args.habit,
        family=args.family,
        native=args.native,
    )
    if args.json:
        _print_json(rows)
        return 0
    print(f"{'ID':<14} {'Habit':<16} {'Family':<18} {'Native':<6} Scientific / Arabic")
    print("-" * 100)
    for r in rows:
        nat = "yes" if r["native_to_iraq"] else "no"
        print(
            f"{r['id']:<14} {(r['habit'] or ''):<16} {(r['family'] or ''):<18} "
            f"{nat:<6} {r['scientific_name']} / {r['arabic']}"
        )
    print(f"\nالمجموع: {len(rows)}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    _print_json(m.get(args.id))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    detail = m.search_detailed(
        args.query or "",
        habit=args.habit,
        family=args.family,
        native=args.native,
        genus=args.genus,
        zone=args.zone,
        presence=args.presence,
        local_status=args.local_status,
        taxon_id=args.id,
        category_group=args.category,
        limit=args.limit,
        offset=args.offset,
    )
    hits = detail["results"]
    if args.json:
        _print_json(detail if args.meta else hits)
        return 0
    for t in hits:
        ar = ""
        ars = (t.get("names") or {}).get("arabic") or []
        if ars and isinstance(ars[0], dict):
            ar = ars[0].get("name", "")
        print(f"{t['id']:<14} {t.get('habit'):<16} {t.get('scientific_name')} — {ar}")
    print(f"\nالنتائج: {detail['count']} / {detail['total']}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=not args.no_backup)
    if args.file:
        raw = m.load_taxon_file(args.file)
    elif args.json:
        raw = json.loads(args.json)
    elif args.interactive:
        raw = _interactive_taxon()
    else:
        raise SystemExit("استخدم --file أو --json أو --interactive")

    # optional id suggestion
    if not raw.get("id") and args.suggest_id:
        cls = raw.get("classification") or {}
        raw["id"] = suggest_id(
            cls.get("family") or "",
            cls.get("genus") or "",
            raw.get("scientific_name") or "",
        )
        print(f"معرّف مقترح: {raw['id']}")

    taxon = m.add(raw)
    print(f"✓ تمت الإضافة: {taxon['id']} — {taxon['scientific_name']}")
    print(f"  العدد الكلي الآن: {m.count()}")
    return 0


def cmd_add_many(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=not args.no_backup)
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "taxa" in data:
        items = data["taxa"]
    elif isinstance(data, list):
        items = data
    else:
        raise SystemExit("الملف يجب أن يكون قائمة أو كائناً فيه taxa")
    added = m.add_many(items)
    print(f"✓ أُضيف {len(added)} صنفاً. العدد الكلي: {m.count()}")
    for t in added:
        print(f"  + {t['id']} — {t['scientific_name']}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=not args.no_backup)
    if args.file:
        patch = json.loads(Path(args.file).read_text(encoding="utf-8"))
    elif args.json:
        patch = json.loads(args.json)
    else:
        patch = _parse_set_args(args.set)
        if not patch:
            raise SystemExit("حدّد --set key=value أو --file أو --json")

    updated = m.update(args.id, patch, replace=args.replace)
    print(f"✓ تم التعديل: {updated['id']} — {updated['scientific_name']}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=not args.no_backup)
    if not args.yes:
        t = m.get(args.id)
        print(f"سيتم حذف: {t['id']} — {t['scientific_name']}")
        ans = input("تأكيد الحذف؟ [y/N]: ").strip().casefold()
        if ans not in ("y", "yes", "ن", "نعم"):
            print("أُلغي الحذف.")
            return 1
    removed = m.delete(args.id)
    print(f"✓ حُذف: {removed['id']} — {removed['scientific_name']}")
    print(f"  العدد الكلي الآن: {m.count()}")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    summary = m.rebuild()
    print("✓ أُعيد بناء كل الملفات المشتقة")
    _print_json(summary)
    return 0


def cmd_suggest_id(args: argparse.Namespace) -> int:
    print(suggest_id(args.family, args.genus, args.scientific_name))
    return 0


def cmd_enums(_: argparse.Namespace) -> int:
    _print_json(
        {
            "habit": ALLOWED_HABIT,
            "presence_in_iraq": ALLOWED_PRESENCE,
            "iraq_local_status": ALLOWED_LOCAL_STATUS,
            "zones": ALLOWED_ZONES,
        }
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    m = FloraManager(auto_backup=False)
    t = m.get(args.id)
    path = Path(args.out) if args.out else Path(f"{t['id']}.json")
    path.write_text(
        json.dumps(t, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"✓ صُدِّر إلى {path}")
    return 0


def _interactive_taxon() -> dict:
    print("=== إدخال صنف تفاعلي ===")
    print("القيم المسموحة للـ habit:")
    for i, h in enumerate(ALLOWED_HABIT, 1):
        print(f"  {i}. {h}")
    sci = input("الاسم العلمي (scientific_name): ").strip()
    family = input("العائلة (family): ").strip()
    genus = input("الجنس (genus): ").strip()
    order = input("الرتبة (order) [اختياري]: ").strip() or "Unknown"
    habit_raw = input("habit (رقم أو نص): ").strip()
    if habit_raw.isdigit() and 1 <= int(habit_raw) <= len(ALLOWED_HABIT):
        habit = ALLOWED_HABIT[int(habit_raw) - 1]
    else:
        habit = habit_raw
    ar = input("الاسم العربي الرئيسي: ").strip()
    en = input("الاسم الإنجليزي (اختياري): ").strip()
    zones_raw = input(
        f"المناطق مفصولة بفاصلة {ALLOWED_ZONES}: "
    ).strip()
    zones = [z.strip() for z in zones_raw.split(",") if z.strip()]
    native_raw = input("أصيل في العراق؟ [Y/n]: ").strip().casefold()
    native = native_raw not in ("n", "no", "لا")
    presence = input("الحضور [موجود]: ").strip() or "موجود"
    status = input("الحالة المحلية [غير_معروف]: ").strip() or "غير_معروف"
    notes = input("ملاحظات: ").strip()
    tid = input("المعرّف id (فارغ = اقتراح تلقائي): ").strip().upper()
    if not tid:
        tid = suggest_id(family, genus, sci)
        print(f"  → {tid}")

    raw: dict[str, Any] = {
        "id": tid,
        "scientific_name": sci,
        "classification": {"order": order, "family": family, "genus": genus},
        "names": {
            "arabic": [{"name": ar, "confidence": "عالية"}] if ar else [],
            "english": [en] if en else [],
        },
        "habit": habit,
        "zones": zones,
        "native_to_iraq": native,
        "presence_in_iraq": presence,
        "iucn": {"category": None, "verified_in_session": False},
        "iraq_local_status": status,
        "notes": notes,
    }
    if not native:
        intro = input("حالة الإدخال/الزراعة: ").strip() or "غير أصيل"
        raw["introduction_status"] = intro
    return raw


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manage_flora",
        description="إدارة أصناف موسوعة الفلورا العراقية — إضافة / تعديل / حذف مع مزامنة كل الملفات",
    )
    p.add_argument(
        "--project-root",
        default=str(PROJECT_ROOT),
        help=argparse.SUPPRESS,
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("stats", help="إحصاءات سريعة")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("list", help="عرض قائمة مختصرة بالأصناف")
    s.add_argument("--habit", choices=ALLOWED_HABIT)
    s.add_argument("--family")
    s.add_argument(
        "--native",
        type=lambda x: {"true": True, "false": False, "1": True, "0": False}[x.lower()],
        default=None,
    )
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("get", help="عرض صنف بالمعرّف")
    s.add_argument("id")
    s.set_defaults(func=cmd_get)

    s = sub.add_parser(
        "search",
        help="بحث متوافق مع المخطط (نصي + تصفية بالحقول)",
    )
    s.add_argument("query", nargs="?", default="", help="نص حر (اختياري مع المرشحات)")
    s.add_argument("--habit", choices=ALLOWED_HABIT)
    s.add_argument("--family")
    s.add_argument("--genus")
    s.add_argument("--zone", choices=ALLOWED_ZONES)
    s.add_argument("--presence", choices=ALLOWED_PRESENCE)
    s.add_argument("--local-status", dest="local_status", choices=ALLOWED_LOCAL_STATUS)
    s.add_argument("--id", help="معرّف أو جزء منه")
    s.add_argument(
        "--category",
        help="مجموعة تصنيفية: trees, shrubs, subshrubs, woody_climbers, herbs, grasses, aquatic",
    )
    s.add_argument(
        "--native",
        type=lambda x: {"true": True, "false": False, "1": True, "0": False}[x.lower()],
        default=None,
    )
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--json", action="store_true")
    s.add_argument("--meta", action="store_true", help="مع --json: إرجاع total/offset/results")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("add", help="إضافة صنف جديد")
    s.add_argument("--file", "-f", help="ملف JSON لصنف واحد")
    s.add_argument("--json", "-j", help="نص JSON مباشر")
    s.add_argument("--interactive", "-i", action="store_true")
    s.add_argument("--suggest-id", action="store_true", help="اقترح id إن لم يوجد")
    s.add_argument("--no-backup", action="store_true")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("add-many", help="إضافة عدة أصناف من ملف واحد")
    s.add_argument("--file", "-f", required=True)
    s.add_argument("--no-backup", action="store_true")
    s.set_defaults(func=cmd_add_many)

    s = sub.add_parser("update", help="تعديل صنف موجود")
    s.add_argument("id")
    s.add_argument("--set", action="append", help="key=value (يُكرر؛ يدعم المفاتيح المنقّطة)")
    s.add_argument("--file", "-f", help="ملف JSON للترقيع أو الاستبدال")
    s.add_argument("--json", "-j")
    s.add_argument(
        "--replace",
        action="store_true",
        help="استبدال السجل بالكامل بدل الدمج",
    )
    s.add_argument("--no-backup", action="store_true")
    s.set_defaults(func=cmd_update)

    s = sub.add_parser("delete", help="حذف صنف")
    s.add_argument("id")
    s.add_argument("--yes", "-y", action="store_true")
    s.add_argument("--no-backup", action="store_true")
    s.set_defaults(func=cmd_delete)

    s = sub.add_parser("rebuild", help="إعادة توليد كل الملفات من الـ master")
    s.set_defaults(func=cmd_rebuild)

    s = sub.add_parser("suggest-id", help="اقتراح معرّف FAM-GEN-SPP")
    s.add_argument("--family", required=True)
    s.add_argument("--genus", required=True)
    s.add_argument("--scientific-name", required=True)
    s.set_defaults(func=cmd_suggest_id)

    s = sub.add_parser("enums", help="عرض القيم المسموحة للحقول التعدادية")
    s.set_defaults(func=cmd_enums)

    s = sub.add_parser("export", help="تصدير صنف إلى ملف JSON")
    s.add_argument("id")
    s.add_argument("--out", "-o")
    s.set_defaults(func=cmd_export)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (NotFoundError, ValidationError, DuplicateError, FloraError) as e:
        print(f"خطأ: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"ملف غير موجود: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"JSON غير صالح: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nأُلغي.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
