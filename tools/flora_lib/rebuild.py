# -*- coding: utf-8 -*-
"""
Rebuild all derived dataset files from the master taxa list.

Single source of truth: data/master/woody_flora.json (+ root mirror).
Derived: by_habit, by_category, by_nativity, by_family, reference, index.
"""

from __future__ import annotations

import re
import shutil
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from .config import (
    ALLOWED_CONFIDENCE,
    ALLOWED_HABIT,
    ALLOWED_LOCAL_STATUS,
    ALLOWED_PRESENCE,
    BY_CATEGORY_DIR,
    BY_FAMILY_DIR,
    BY_HABIT_DIR,
    BY_NATIVITY_DIR,
    CATEGORY_GROUPS,
    DATA_DIR,
    HABIT_FILES,
    INDEX_PATH,
    MASTER_PATH,
    PLACEHOLDER_CATEGORIES,
    PROJECT_ROOT,
    REF_DIR,
    ROOT_MASTER_PATH,
    SCHEMA_VERSION,
)
from .io_utils import dump_json, load_json


def sort_taxa(taxa: list[dict]) -> list[dict]:
    def key(t: dict) -> tuple:
        cls = t.get("classification") or {}
        return (
            (cls.get("family") or "").casefold(),
            (cls.get("genus") or "").casefold(),
            (t.get("scientific_name") or "").casefold(),
            t.get("id") or "",
        )

    return sorted(taxa, key=key)


def make_file_meta(
    *,
    title_ar: str,
    title_en: str,
    subset: str,
    count: int,
    parent: str,
    extra: dict | None = None,
) -> dict:
    m: dict[str, Any] = {
        "project": "Iraqi Flora Encyclopedia / موسوعة الفلورا العراقية",
        "phase": "managed-dataset",
        "title_ar": title_ar,
        "title_en": title_en,
        "subset": subset,
        "taxa_count": count,
        "parent_dataset": parent,
        "updated_on": date.today().isoformat(),
        "language_convention": "التنوين يُرسم على الحرف الأخير دائماً (حقاً لا حقًا)",
        "schema_ref": "schema/plant_taxon.schema.json",
    }
    if extra:
        m.update(extra)
    return m


def wrap_taxa_file(meta: dict, taxa: list[dict], **extra: Any) -> dict:
    out: dict[str, Any] = {
        "$schema_version": SCHEMA_VERSION,
        "meta": meta,
        "taxa": taxa,
    }
    out.update(extra)
    return out


def _clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _family_slug(family: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", family or "Unknown").strip("_") or "Unknown"


def update_master_meta(meta: dict | None, taxa: list[dict]) -> dict:
    meta = deepcopy(meta) if meta else {}
    meta.setdefault("title_ar", "الأشجار والشجيرات الأصيلة في الفلورا العراقية")
    meta.setdefault("title_en", "Native Trees and Shrubs of the Iraqi Flora")
    meta.setdefault(
        "project", "Iraqi Flora Encyclopedia / موسوعة الفلورا العراقية"
    )
    meta["schema_version_dataset"] = SCHEMA_VERSION
    meta["updated_on"] = date.today().isoformat()
    meta.setdefault("scope", {})
    meta["scope"]["taxa_count"] = len(taxa)
    meta["field_definitions"] = {
        "presence_in_iraq": ALLOWED_PRESENCE,
        "iraq_local_status": ALLOWED_LOCAL_STATUS,
        "confidence": ALLOWED_CONFIDENCE,
        "habit": ALLOWED_HABIT,
        "iucn_category": ["LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE", None],
        "category_groups": {
            "tree": ["شجرة", "شجرة_صغيرة"],
            "shrub": ["شجيرة", "شجيرة_شوكية", "شجيرة_ملحية"],
            "subshrub": ["شبه_شجيرة"],
            "climber": ["متسلق_خشبي"],
            "herb": ["عشبة_معمّرة", "عشبة_حولية"],
            "grass": ["نجيلة_أو_عشب"],
            "aquatic": ["مائي"],
        },
    }
    meta["file_layout"] = {
        "master": "data/master/woody_flora.json",
        "by_habit": "data/by_habit/",
        "by_category_group": "data/by_category/",
        "by_nativity": "data/by_nativity/",
        "by_family": "data/by_family/",
        "reference": "data/reference/",
        "schema": "schema/",
        "manager": "tools/manage_flora.py",
    }
    return meta


def build_master_document(
    taxa: list[dict],
    *,
    meta: dict | None = None,
    vegetation_zones: list | None = None,
    analysis: dict | None = None,
) -> dict:
    taxa = sort_taxa(list(taxa))
    return {
        "$schema_version": SCHEMA_VERSION,
        "meta": update_master_meta(meta, taxa),
        "vegetation_zones": vegetation_zones or [],
        "taxa": taxa,
        "analysis": analysis if analysis is not None else {},
    }


def rebuild_all(
    master: dict,
    *,
    write_root_mirror: bool = True,
) -> dict[str, Any]:
    """
    Write master + every derived file. Returns a summary dict.
    """
    taxa = sort_taxa(list(master.get("taxa") or []))
    meta = update_master_meta(master.get("meta"), taxa)
    vegetation_zones = master.get("vegetation_zones") or []
    analysis = master.get("analysis") if master.get("analysis") is not None else {}

    master_doc = {
        "$schema_version": SCHEMA_VERSION,
        "meta": meta,
        "vegetation_zones": vegetation_zones,
        "taxa": taxa,
        "analysis": analysis,
    }

    # Master copies
    dump_json(MASTER_PATH, master_doc)
    if write_root_mirror:
        dump_json(ROOT_MASTER_PATH, master_doc)

    # Reference slices
    _clear_dir(REF_DIR)
    dump_json(
        REF_DIR / "vegetation_zones.json",
        {
            "$schema_version": SCHEMA_VERSION,
            "meta": make_file_meta(
                title_ar="المناطق النباتية في العراق",
                title_en="Vegetation Zones of Iraq",
                subset="vegetation_zones",
                count=len(vegetation_zones),
                parent="data/master/woody_flora.json",
            ),
            "vegetation_zones": vegetation_zones,
        },
    )
    dump_json(
        REF_DIR / "analysis.json",
        {
            "$schema_version": SCHEMA_VERSION,
            "meta": make_file_meta(
                title_ar="تحليلات وتوصيات منهجية",
                title_en="Analysis and Methodological Notes",
                subset="analysis",
                count=len(analysis) if isinstance(analysis, dict) else 0,
                parent="data/master/woody_flora.json",
            ),
            "analysis": analysis,
        },
    )
    dump_json(
        REF_DIR / "meta.json",
        {"$schema_version": SCHEMA_VERSION, "meta": meta},
    )

    # by_habit
    _clear_dir(BY_HABIT_DIR)
    by_habit: dict[str, list] = defaultdict(list)
    for t in taxa:
        by_habit[t.get("habit")].append(t)

    habit_index = []
    for habit, conf in HABIT_FILES.items():
        group = sort_taxa(by_habit.get(habit, []))
        dump_json(
            BY_HABIT_DIR / f"{conf['file']}.json",
            wrap_taxa_file(
                make_file_meta(
                    title_ar=f"الفلورا الخشبية العراقية — {conf['label_ar']}",
                    title_en=f"Iraqi Woody Flora — {conf['label_en']}",
                    subset=f"habit:{habit}",
                    count=len(group),
                    parent="data/master/woody_flora.json",
                    extra={
                        "habit": habit,
                        "habit_label_ar": conf["label_ar"],
                        "habit_label_en": conf["label_en"],
                        "category_group": conf["category_group"],
                    },
                ),
                group,
            ),
        )
        habit_index.append(
            {
                "habit": habit,
                "file": f"data/by_habit/{conf['file']}.json",
                "count": len(group),
                "label_ar": conf["label_ar"],
                "label_en": conf["label_en"],
            }
        )

    # by_category
    _clear_dir(BY_CATEGORY_DIR)
    cat_index = []
    for gkey, gconf in CATEGORY_GROUPS.items():
        group = sort_taxa([t for t in taxa if t.get("habit") in gconf["habits"]])
        dump_json(
            BY_CATEGORY_DIR / f"{gconf['file']}.json",
            wrap_taxa_file(
                make_file_meta(
                    title_ar=f"الفلورا الخشبية العراقية — {gconf['label_ar']}",
                    title_en=f"Iraqi Woody Flora — {gconf['label_en']}",
                    subset=f"category_group:{gkey}",
                    count=len(group),
                    parent="data/master/woody_flora.json",
                    extra={
                        "category_group": gkey,
                        "included_habits": gconf["habits"],
                    },
                ),
                group,
            ),
        )
        cat_index.append(
            {
                "category_group": gkey,
                "file": f"data/by_category/{gconf['file']}.json",
                "count": len(group),
                "habits": gconf["habits"],
                "label_ar": gconf["label_ar"],
                "label_en": gconf["label_en"],
            }
        )

    for slug, ar, en in PLACEHOLDER_CATEGORIES:
        dump_json(
            BY_CATEGORY_DIR / f"{slug}.json",
            wrap_taxa_file(
                make_file_meta(
                    title_ar=ar,
                    title_en=en,
                    subset=f"category_group:{slug}",
                    count=0,
                    parent="data/master/woody_flora.json",
                    extra={
                        "status": "placeholder",
                        "reason": "Source dataset is woody-only for now.",
                    },
                ),
                [],
            ),
        )
        cat_index.append(
            {
                "category_group": slug,
                "file": f"data/by_category/{slug}.json",
                "count": 0,
                "status": "placeholder",
                "label_ar": ar,
                "label_en": en,
            }
        )

    # by_nativity
    _clear_dir(BY_NATIVITY_DIR)
    native = sort_taxa([t for t in taxa if t.get("native_to_iraq")])
    non_native = sort_taxa([t for t in taxa if not t.get("native_to_iraq")])
    dump_json(
        BY_NATIVITY_DIR / "native.json",
        wrap_taxa_file(
            make_file_meta(
                title_ar="أنواع أصيلة في العراق",
                title_en="Native-to-Iraq Taxa",
                subset="native_to_iraq:true",
                count=len(native),
                parent="data/master/woody_flora.json",
            ),
            native,
        ),
    )
    dump_json(
        BY_NATIVITY_DIR / "non_native.json",
        wrap_taxa_file(
            make_file_meta(
                title_ar="أنواع غير أصيلة (مزروعة / مُدخَلة / غازية)",
                title_en="Non-native Taxa",
                subset="native_to_iraq:false",
                count=len(non_native),
                parent="data/master/woody_flora.json",
            ),
            non_native,
        ),
    )

    # by_family
    _clear_dir(BY_FAMILY_DIR)
    families: dict[str, list] = defaultdict(list)
    for t in taxa:
        fam = (t.get("classification") or {}).get("family") or "Unknown"
        families[fam].append(t)

    family_index = []
    for fam in sorted(families.keys(), key=str.casefold):
        group = sort_taxa(families[fam])
        slug = _family_slug(fam)
        dump_json(
            BY_FAMILY_DIR / f"{slug}.json",
            wrap_taxa_file(
                make_file_meta(
                    title_ar=f"العائلة {fam}",
                    title_en=f"Family {fam}",
                    subset=f"family:{fam}",
                    count=len(group),
                    parent="data/master/woody_flora.json",
                    extra={"family": fam},
                ),
                group,
            ),
        )
        family_index.append(
            {
                "family": fam,
                "file": f"data/by_family/{slug}.json",
                "count": len(group),
            }
        )

    habit_counts = dict(Counter(t.get("habit") for t in taxa))
    index = {
        "$schema_version": SCHEMA_VERSION,
        "project": "Iraqi Flora Encyclopedia",
        "generated_on": date.today().isoformat(),
        "master": "data/master/woody_flora.json",
        "schema": {
            "taxon": "schema/plant_taxon.schema.json",
            "dataset": "schema/woody_flora_dataset.schema.json",
            "field_catalog": "schema/field_catalog.json",
        },
        "manager": "tools/manage_flora.py",
        "totals": {
            "taxa": len(taxa),
            "native": len(native),
            "non_native": len(non_native),
            "families": len(families),
            "vegetation_zones": len(vegetation_zones),
        },
        "by_habit": habit_index,
        "by_category": cat_index,
        "by_nativity": [
            {"file": "data/by_nativity/native.json", "count": len(native)},
            {"file": "data/by_nativity/non_native.json", "count": len(non_native)},
        ],
        "by_family": family_index,
        "reference": [
            "data/reference/vegetation_zones.json",
            "data/reference/analysis.json",
            "data/reference/meta.json",
        ],
        "habit_counts": habit_counts,
    }
    dump_json(INDEX_PATH, index)

    return {
        "taxa": len(taxa),
        "native": len(native),
        "non_native": len(non_native),
        "families": len(families),
        "habit_counts": habit_counts,
        "master": str(MASTER_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "index": str(INDEX_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }


def load_master() -> dict:
    if MASTER_PATH.exists():
        return load_json(MASTER_PATH)
    if ROOT_MASTER_PATH.exists():
        return load_json(ROOT_MASTER_PATH)
    raise FileNotFoundError(
        f"لم يُعثر على الملف الرئيسي: {MASTER_PATH} أو {ROOT_MASTER_PATH}"
    )
