# -*- coding: utf-8 -*-
"""Normalize and validate plant taxon entries."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .config import (
    ALLOWED_CONFIDENCE,
    ALLOWED_HABIT,
    ALLOWED_LOCAL_STATUS,
    ALLOWED_PRESENCE,
    ALLOWED_ZONES,
    ID_PATTERN,
    IUCN_CODES,
    STANDARD_TAXON_KEYS,
)
from .errors import ValidationError


def _strip_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_name_list(items: Any, *, conf_default: str = "متوسطة") -> list[dict]:
    out: list[dict] = []
    for item in items or []:
        if isinstance(item, str):
            name = item.strip()
            if name:
                out.append({"name": name, "confidence": conf_default})
            continue
        if not isinstance(item, dict):
            continue
        name = _strip_str(item.get("name"))
        if not name:
            continue
        conf = item.get("confidence", conf_default)
        if conf not in ALLOWED_CONFIDENCE:
            conf = conf_default
        out.append({"name": name, "confidence": conf})
    return out


def normalize_english(items: Any) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict) and item.get("name"):
            s = _strip_str(item["name"])
            if s:
                out.append(s)
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        key = s.casefold()
        if key not in seen:
            seen.add(key)
            uniq.append(s)
    return uniq


def normalize_iucn(iucn: Any) -> dict:
    if not isinstance(iucn, dict):
        iucn = {}
    cat = iucn.get("category")
    note = _strip_str(iucn.get("note")) or None
    verified = bool(iucn.get("verified_in_session", False))
    assessment_noted = bool(iucn.get("assessment_noted", False))

    if cat == "مُقيَّم":
        assessment_noted = True
        extra = "تقييم منشور لدى IUCN لكن الرتبة النهائية غير مثبتة في الجلسة"
        note = f"{extra}. {note}" if note else extra
        cat = None
        verified = False

    if cat in ("", "null", "None"):
        cat = None

    if cat is not None and cat not in IUCN_CODES:
        extra = f"قيمة IUCN غير معيارية أُزيلت: {cat!r}"
        note = f"{note}. {extra}" if note else extra
        cat = None
        verified = False

    if cat is None:
        verified = False

    out: dict[str, Any] = {
        "category": cat,
        "verified_in_session": verified,
    }
    if assessment_noted:
        out["assessment_noted"] = True
    if note:
        out["note"] = note
    return out


def normalize_classification(cls: Any) -> dict:
    if not isinstance(cls, dict):
        cls = {}
    family = _strip_str(cls.get("family")) or None
    # peel parenthetical annotation into pure family name
    family_ann = None
    if family and "(" in family and family.endswith(")"):
        base, rest = family.split("(", 1)
        family = base.strip() or None
        family_ann = rest[:-1].strip() or None

    out: dict[str, Any] = {
        "order": _strip_str(cls.get("order")) or None,
        "family": family,
        "genus": _strip_str(cls.get("genus")) or None,
    }
    for opt in ("division", "class", "subgenus", "section"):
        val = cls.get(opt)
        if val:
            out[opt] = _strip_str(val)
    if family_ann:
        out["_family_annotation"] = family_ann  # temporary; folded later
    return out


def ordered_taxon(t: dict) -> dict:
    out: dict[str, Any] = {}
    for k in STANDARD_TAXON_KEYS:
        if k in t:
            out[k] = t[k]
    for k, v in t.items():
        if k not in out and not k.startswith("_"):
            out[k] = v
    return out


def normalize_taxon(raw: dict, *, strict: bool = True) -> dict:
    """
    Normalize a taxon dict to the project schema.
    Raises ValidationError if strict and required fields fail.
    """
    if not isinstance(raw, dict):
        raise ValidationError("المدخل يجب أن يكون كائناً JSON (dict)")

    errors: list[str] = []
    t: dict[str, Any] = {}

    tid = _strip_str(raw.get("id")).upper().replace("_", "-")
    if not tid:
        errors.append("الحقل id مطلوب")
    elif not re.match(ID_PATTERN, tid):
        errors.append(
            f"صيغة id غير صالحة: {tid!r} — المتوقع مثل FAG-QUE-AEG (3-3-2/4 حروف لاتينية كبيرة)"
        )
    t["id"] = tid

    sci = " ".join(_strip_str(raw.get("scientific_name")).split())
    if not sci:
        errors.append("الحقل scientific_name مطلوب")
    t["scientific_name"] = sci

    tax_note = _strip_str(raw.get("taxonomic_note"))
    if tax_note:
        t["taxonomic_note"] = tax_note

    cls = normalize_classification(raw.get("classification"))
    family_ann = cls.pop("_family_annotation", None)
    t["classification"] = {
        k: v for k, v in cls.items() if not k.startswith("_")
    }
    if not t["classification"].get("order"):
        errors.append("classification.order مطلوب")
    if not t["classification"].get("family"):
        errors.append("classification.family مطلوب")
    if not t["classification"].get("genus"):
        errors.append("classification.genus مطلوب")

    if family_ann:
        fam_note = (
            f"العائلة في المصدر مُعلَّقة: "
            f"{t['classification'].get('family')} ({family_ann})"
        )
        if t.get("taxonomic_note"):
            if fam_note not in t["taxonomic_note"]:
                t["taxonomic_note"] = f"{t['taxonomic_note']} | {fam_note}"
        else:
            t["taxonomic_note"] = fam_note

    names_in = raw.get("names") if isinstance(raw.get("names"), dict) else {}
    arabic = normalize_name_list(names_in.get("arabic"))
    english = normalize_english(names_in.get("english"))
    kurdish = normalize_name_list(names_in.get("kurdish"))
    names: dict[str, Any] = {"arabic": arabic, "english": english}
    if kurdish:
        names["kurdish"] = kurdish
    t["names"] = names
    if not arabic:
        errors.append("names.arabic مطلوب (قائمة اسم واحد على الأقل)")

    habit = raw.get("habit")
    if habit not in ALLOWED_HABIT:
        errors.append(
            f"habit غير صالح: {habit!r}. المسموح: {', '.join(ALLOWED_HABIT)}"
        )
    t["habit"] = habit

    zones = raw.get("zones") or []
    if isinstance(zones, str):
        zones = [zones]
    zones = [str(z).strip() for z in zones if str(z).strip()]
    bad_z = [z for z in zones if z not in ALLOWED_ZONES]
    if bad_z:
        errors.append(f"zones غير معروفة: {bad_z}. المسموح: {ALLOWED_ZONES}")
    if not zones:
        errors.append("zones مطلوب (قائمة منطقة واحدة على الأقل)")
    t["zones"] = zones

    if "native_to_iraq" not in raw:
        errors.append("native_to_iraq مطلوب (true/false)")
        native = True
    else:
        native = bool(raw.get("native_to_iraq"))
    t["native_to_iraq"] = native

    if "endemic_to_iraq" in raw:
        t["endemic_to_iraq"] = bool(raw["endemic_to_iraq"])

    presence = raw.get("presence_in_iraq")
    if presence not in ALLOWED_PRESENCE:
        errors.append(
            f"presence_in_iraq غير صالح: {presence!r}. المسموح: {ALLOWED_PRESENCE}"
        )
    t["presence_in_iraq"] = presence

    intro = _strip_str(raw.get("introduction_status"))
    if not native:
        if not intro:
            intro = "غير أصيل / حالة غير مفصّلة"
        t["introduction_status"] = intro
    elif intro:
        t["introduction_status"] = intro

    t["iucn"] = normalize_iucn(raw.get("iucn"))

    status = raw.get("iraq_local_status")
    if status not in ALLOWED_LOCAL_STATUS:
        errors.append(
            f"iraq_local_status غير صالح: {status!r}. المسموح: {ALLOWED_LOCAL_STATUS}"
        )
    t["iraq_local_status"] = status

    flag = _strip_str(raw.get("flag"))
    if flag:
        t["flag"] = flag

    if raw.get("flagship_case") is True:
        t["flagship_case"] = True
    elif raw.get("flagship_case") is False:
        pass  # omit false

    t["notes"] = _strip_str(raw.get("notes"))

    if errors and strict:
        raise ValidationError("فشل التحقق من المدخل:\n- " + "\n- ".join(errors))

    return ordered_taxon(t)


def deep_merge(base: dict, patch: dict) -> dict:
    """Merge patch into base (nested dicts merged; other values replaced)."""
    result = deepcopy(base)
    for key, value in patch.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def suggest_id(family: str, genus: str, scientific_name: str) -> str:
    """Suggest FAM-GEN-SPP style id from classification + species epithet."""
    fam = re.sub(r"[^A-Za-z]", "", family or "")[:3].upper().ljust(3, "X")
    gen = re.sub(r"[^A-Za-z]", "", genus or "")[:3].upper().ljust(3, "X")
    parts = (scientific_name or "").split()
    epithet = parts[1] if len(parts) >= 2 else (parts[0] if parts else "SP")
    spp = re.sub(r"[^A-Za-z0-9]", "", epithet)[:3].upper().ljust(3, "X")
    return f"{fam}-{gen}-{spp}"
