# -*- coding: utf-8 -*-
"""
Schema-aware search engine for Iraqi Flora taxa.

Queries align with the plant_taxon schema and field_catalog:
  - Free-text across id, scientific name, local names, notes, classification
  - Structured filters on enum/boolean/array fields defined in the schema
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import CATEGORY_GROUPS, HABIT_FILES


# Fields that free-text search inspects (schema-aligned paths)
SEARCHABLE_PATHS: tuple[str, ...] = (
    "id",
    "scientific_name",
    "taxonomic_note",
    "notes",
    "habit",
    "flag",
    "introduction_status",
    "presence_in_iraq",
    "iraq_local_status",
    "classification.order",
    "classification.family",
    "classification.genus",
    "classification.division",
    "classification.class",
    "names.arabic",
    "names.kurdish",
    "names.english",
    "zones",
    "iucn.category",
    "iucn.note",
)


@dataclass
class SearchQuery:
    """Structured, schema-aware query for taxa."""

    text: str = ""
    id: str | None = None
    scientific_name: str | None = None
    habit: str | None = None
    family: str | None = None
    genus: str | None = None
    order: str | None = None
    zone: str | None = None
    native: bool | None = None
    endemic: bool | None = None
    presence: str | None = None
    local_status: str | None = None
    iucn: str | None = None
    flagship: bool | None = None
    category_group: str | None = None  # trees | shrubs | herbs | …
    limit: int = 200
    offset: int = 0
    sort_by: str = "family"  # family | scientific_name | id | habit
    sort_desc: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "SearchQuery":
        """Build from a flat dict (CLI / HTTP query string)."""

        def _bool(v: Any) -> bool | None:
            if v is None or v == "":
                return None
            if isinstance(v, bool):
                return v
            s = str(v).strip().casefold()
            if s in ("true", "1", "yes", "y", "نعم"):
                return True
            if s in ("false", "0", "no", "n", "لا"):
                return False
            return None

        def _str(key: str) -> str | None:
            v = params.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return s or None

        def _int(key: str, default: int) -> int:
            v = params.get(key)
            if v is None or v == "":
                return default
            try:
                return max(0, int(v))
            except (TypeError, ValueError):
                return default

        text = _str("q") or _str("query") or _str("text") or ""
        return cls(
            text=text,
            id=_str("id"),
            scientific_name=_str("scientific_name"),
            habit=_str("habit"),
            family=_str("family"),
            genus=_str("genus"),
            order=_str("order"),
            zone=_str("zone") or _str("zones"),
            native=_bool(params.get("native") if "native" in params else params.get("native_to_iraq")),
            endemic=_bool(params.get("endemic") if "endemic" in params else params.get("endemic_to_iraq")),
            presence=_str("presence") or _str("presence_in_iraq"),
            local_status=_str("local_status") or _str("iraq_local_status"),
            iucn=_str("iucn") or _str("iucn_category"),
            flagship=_bool(params.get("flagship") if "flagship" in params else params.get("flagship_case")),
            category_group=_str("category") or _str("category_group"),
            limit=_int("limit", 200),
            offset=_int("offset", 0),
            sort_by=_str("sort_by") or "family",
            sort_desc=bool(_bool(params.get("sort_desc")) or False),
        )


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _flatten_value(value: Any) -> list[str]:
    """Turn nested name lists / scalars into searchable strings."""
    out: list[str] = []
    if value is None:
        return out
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, (int, float, bool)):
        out.append(str(value))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    out.append(str(name))
                else:
                    out.extend(_flatten_value(item))
            else:
                out.extend(_flatten_value(item))
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_value(v))
    return out


def taxon_search_blob(taxon: dict) -> str:
    """Concatenate all searchable schema fields for free-text matching."""
    parts: list[str] = []
    for path in SEARCHABLE_PATHS:
        parts.extend(_flatten_value(_get_path(taxon, path)))
    return " ".join(parts).casefold()


def habit_in_category(habit: str | None, category_group: str) -> bool:
    key = (category_group or "").strip().casefold()
    if not key:
        return True
    # allow CATEGORY_GROUPS keys or HABIT_FILES category_group values
    if key in CATEGORY_GROUPS:
        return habit in CATEGORY_GROUPS[key]["habits"]
    for g in CATEGORY_GROUPS.values():
        if g["file"].casefold() == key or g["label_en"].casefold() == key:
            return habit in g["habits"]
    # match HABIT_FILES category_group label (tree, shrub, herb, …)
    meta = HABIT_FILES.get(habit or "")
    if meta and meta.get("category_group", "").casefold() == key:
        return True
    return False


class SchemaAwareSearch:
    """Filter and rank taxa according to schema field structure."""

    def __init__(self, taxa: Iterable[dict] | None = None) -> None:
        self._taxa: list[dict] = list(taxa or [])

    def set_taxa(self, taxa: Iterable[dict]) -> None:
        self._taxa = list(taxa)

    def search(self, query: SearchQuery | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Run a schema-aware search.

        Returns:
          {
            "total": int,          # matches before pagination
            "count": int,          # page size
            "offset": int,
            "limit": int,
            "results": [taxon, ...]
          }
        """
        if query is None:
            query = SearchQuery.from_params(kwargs)
        elif kwargs:
            # merge kwargs over existing query fields
            base = SearchQuery.from_params({**query.__dict__, **kwargs})
            query = base

        q_text = (query.text or "").strip().casefold()
        tokens = [t for t in q_text.split() if t]

        matched: list[dict] = []
        for t in self._taxa:
            if not self._passes_filters(t, query):
                continue
            if tokens and not self._text_match(t, tokens):
                continue
            matched.append(t)

        matched = self._sort(matched, query.sort_by, query.sort_desc)
        total = len(matched)
        # Soft safety cap; callers (HTTP) should pass smaller page sizes
        limit = max(1, min(int(query.limit or 200), 100_000))
        offset = max(0, int(query.offset or 0))
        page = matched[offset : offset + limit]

        return {
            "total": total,
            "count": len(page),
            "offset": offset,
            "limit": limit,
            "results": [deepcopy(t) for t in page],
        }

    def filter_only(self, **filters: Any) -> list[dict]:
        """Convenience: return full match list without pagination metadata."""
        q = SearchQuery.from_params(filters)
        q.limit = 100_000
        q.offset = 0
        return self.search(q)["results"]

    # ------------------------------------------------------------------ internals
    def _passes_filters(self, t: dict, query: SearchQuery) -> bool:
        if query.id:
            if (t.get("id") or "").casefold() != query.id.casefold():
                # allow partial id match (prefix / contains)
                if query.id.casefold() not in (t.get("id") or "").casefold():
                    return False

        if query.scientific_name:
            sci = (t.get("scientific_name") or "").casefold()
            if query.scientific_name.casefold() not in sci:
                return False

        if query.habit and t.get("habit") != query.habit:
            return False

        cls = t.get("classification") or {}
        if query.family:
            fam = (cls.get("family") or "").casefold()
            if fam != query.family.casefold():
                return False
        if query.genus:
            gen = (cls.get("genus") or "").casefold()
            if gen != query.genus.casefold():
                return False
        if query.order:
            ord_ = (cls.get("order") or "").casefold()
            if ord_ != query.order.casefold():
                return False

        if query.zone:
            zones = [str(z).casefold() for z in (t.get("zones") or [])]
            if query.zone.casefold() not in zones:
                return False

        if query.native is not None and bool(t.get("native_to_iraq")) != query.native:
            return False
        if query.endemic is not None and bool(t.get("endemic_to_iraq")) != query.endemic:
            return False

        if query.presence and t.get("presence_in_iraq") != query.presence:
            return False
        if query.local_status and t.get("iraq_local_status") != query.local_status:
            return False

        if query.iucn is not None:
            cat = (t.get("iucn") or {}).get("category")
            want = query.iucn.strip().upper()
            if want in ("NULL", "NONE", "-"):
                if cat is not None:
                    return False
            elif (cat or "").upper() != want:
                return False

        if query.flagship is not None and bool(t.get("flagship_case")) != query.flagship:
            return False

        if query.category_group and not habit_in_category(
            t.get("habit"), query.category_group
        ):
            return False

        return True

    def _text_match(self, t: dict, tokens: list[str]) -> bool:
        blob = taxon_search_blob(t)
        # all tokens must appear (AND)
        return all(tok in blob for tok in tokens)

    def _sort(self, rows: list[dict], sort_by: str, desc: bool) -> list[dict]:
        key = (sort_by or "family").casefold()

        def sort_key(t: dict) -> tuple:
            cls = t.get("classification") or {}
            if key == "id":
                return (t.get("id") or "",)
            if key in ("scientific_name", "name", "sci"):
                return ((t.get("scientific_name") or "").casefold(),)
            if key == "habit":
                return (t.get("habit") or "", t.get("scientific_name") or "")
            if key == "genus":
                return (
                    (cls.get("genus") or "").casefold(),
                    (t.get("scientific_name") or "").casefold(),
                )
            # default family → genus → scientific
            return (
                (cls.get("family") or "").casefold(),
                (cls.get("genus") or "").casefold(),
                (t.get("scientific_name") or "").casefold(),
            )

        return sorted(rows, key=sort_key, reverse=desc)


def summarize_taxon(t: dict) -> dict[str, Any]:
    """Compact row for list/table views."""
    ar_names = (t.get("names") or {}).get("arabic") or []
    ar0 = ar_names[0]["name"] if ar_names and isinstance(ar_names[0], dict) else ""
    en_names = (t.get("names") or {}).get("english") or []
    en0 = en_names[0] if en_names else ""
    cls = t.get("classification") or {}
    iucn = t.get("iucn") or {}
    return {
        "id": t.get("id"),
        "scientific_name": t.get("scientific_name"),
        "arabic": ar0,
        "english": en0,
        "habit": t.get("habit"),
        "family": cls.get("family"),
        "genus": cls.get("genus"),
        "order": cls.get("order"),
        "zones": list(t.get("zones") or []),
        "native_to_iraq": t.get("native_to_iraq"),
        "presence_in_iraq": t.get("presence_in_iraq"),
        "iraq_local_status": t.get("iraq_local_status"),
        "iucn_category": iucn.get("category"),
        "flagship_case": bool(t.get("flagship_case")),
        "flag": t.get("flag"),
    }
