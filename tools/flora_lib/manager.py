# -*- coding: utf-8 -*-
"""
FloraManager — single API for add / update / delete with automatic fan-out.

Workflow:
  1. Load master (source of truth)
  2. Mutate taxa list in memory
  3. rebuild_all() writes master + every derived file
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import ARCHIVE_DIR, MASTER_PATH, PROJECT_ROOT
from .errors import DuplicateError, NotFoundError, ValidationError
from .rebuild import load_master, rebuild_all, sort_taxa
from .validate import deep_merge, normalize_taxon, suggest_id


class FloraManager:
    """Automatic multi-file management for Iraqi Flora taxa."""

    def __init__(self, *, auto_backup: bool = True) -> None:
        self.auto_backup = auto_backup
        self._master: dict | None = None

    # ------------------------------------------------------------------ load
    def load(self, *, force: bool = False) -> dict:
        if self._master is None or force:
            self._master = load_master()
        return self._master

    @property
    def master(self) -> dict:
        return self.load()

    @property
    def taxa(self) -> list[dict]:
        return list(self.master.get("taxa") or [])

    def count(self) -> int:
        return len(self.taxa)

    # ------------------------------------------------------------------ query
    def get(self, taxon_id: str) -> dict:
        tid = taxon_id.strip().upper()
        for t in self.taxa:
            if t.get("id") == tid:
                return deepcopy(t)
        raise NotFoundError(f"لا يوجد صنف بالمعرّف: {tid}")

    def find_by_scientific_name(self, name: str) -> dict | None:
        key = " ".join(name.split()).casefold()
        for t in self.taxa:
            if (t.get("scientific_name") or "").casefold() == key:
                return deepcopy(t)
        return None

    def search(
        self,
        query: str,
        *,
        habit: str | None = None,
        family: str | None = None,
        native: bool | None = None,
        limit: int = 50,
    ) -> list[dict]:
        q = (query or "").strip().casefold()
        results: list[dict] = []
        for t in self.taxa:
            if habit and t.get("habit") != habit:
                continue
            if family:
                fam = (t.get("classification") or {}).get("family") or ""
                if fam.casefold() != family.casefold():
                    continue
            if native is not None and bool(t.get("native_to_iraq")) != native:
                continue
            if q and not self._matches(t, q):
                continue
            results.append(deepcopy(t))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _matches(t: dict, q: str) -> bool:
        hay = [
            t.get("id") or "",
            t.get("scientific_name") or "",
            t.get("notes") or "",
            t.get("habit") or "",
            (t.get("classification") or {}).get("family") or "",
            (t.get("classification") or {}).get("genus") or "",
        ]
        for ar in (t.get("names") or {}).get("arabic") or []:
            if isinstance(ar, dict):
                hay.append(ar.get("name") or "")
        for en in (t.get("names") or {}).get("english") or []:
            hay.append(str(en))
        for ku in (t.get("names") or {}).get("kurdish") or []:
            if isinstance(ku, dict):
                hay.append(ku.get("name") or "")
        blob = " ".join(hay).casefold()
        return q in blob

    def stats(self) -> dict[str, Any]:
        taxa = self.taxa
        by_habit: dict[str, int] = {}
        by_family: dict[str, int] = {}
        native = 0
        for t in taxa:
            h = t.get("habit") or "?"
            by_habit[h] = by_habit.get(h, 0) + 1
            fam = (t.get("classification") or {}).get("family") or "?"
            by_family[fam] = by_family.get(fam, 0) + 1
            if t.get("native_to_iraq"):
                native += 1
        return {
            "total": len(taxa),
            "native": native,
            "non_native": len(taxa) - native,
            "families": len(by_family),
            "by_habit": dict(sorted(by_habit.items(), key=lambda x: -x[1])),
            "top_families": sorted(by_family.items(), key=lambda x: -x[1])[:15],
        }

    def list_ids(self) -> list[str]:
        return [t["id"] for t in sort_taxa(self.taxa)]

    def list_summaries(
        self,
        *,
        habit: str | None = None,
        family: str | None = None,
        native: bool | None = None,
    ) -> list[dict]:
        rows = []
        for t in sort_taxa(self.taxa):
            if habit and t.get("habit") != habit:
                continue
            if family:
                fam = (t.get("classification") or {}).get("family") or ""
                if fam.casefold() != family.casefold():
                    continue
            if native is not None and bool(t.get("native_to_iraq")) != native:
                continue
            ar_names = (t.get("names") or {}).get("arabic") or []
            ar0 = ar_names[0]["name"] if ar_names and isinstance(ar_names[0], dict) else ""
            rows.append(
                {
                    "id": t.get("id"),
                    "scientific_name": t.get("scientific_name"),
                    "arabic": ar0,
                    "habit": t.get("habit"),
                    "family": (t.get("classification") or {}).get("family"),
                    "native_to_iraq": t.get("native_to_iraq"),
                }
            )
        return rows

    # ------------------------------------------------------------------ mutate
    def add(self, raw: dict, *, strict: bool = True) -> dict:
        """Add a new taxon and sync all files. Returns the normalized taxon."""
        taxon = normalize_taxon(raw, strict=strict)
        self.load()
        self._assert_unique(taxon["id"], taxon["scientific_name"])
        master = deepcopy(self._master)
        taxa = list(master.get("taxa") or [])
        taxa.append(taxon)
        master["taxa"] = taxa
        self._commit(master, action="add", taxon_id=taxon["id"])
        return deepcopy(taxon)

    def add_many(self, raw_list: Iterable[dict], *, strict: bool = True) -> list[dict]:
        """Add multiple taxa in one rebuild cycle."""
        self.load()
        master = deepcopy(self._master)
        taxa = list(master.get("taxa") or [])
        existing_ids = {t["id"] for t in taxa}
        existing_sci = {t["scientific_name"].casefold() for t in taxa}
        added: list[dict] = []
        for raw in raw_list:
            taxon = normalize_taxon(raw, strict=strict)
            if taxon["id"] in existing_ids:
                raise DuplicateError(f"معرّف مكرر: {taxon['id']}")
            if taxon["scientific_name"].casefold() in existing_sci:
                raise DuplicateError(
                    f"اسم علمي مكرر: {taxon['scientific_name']}"
                )
            taxa.append(taxon)
            existing_ids.add(taxon["id"])
            existing_sci.add(taxon["scientific_name"].casefold())
            added.append(taxon)
        master["taxa"] = taxa
        self._commit(
            master,
            action="add_many",
            taxon_id=",".join(t["id"] for t in added),
        )
        return deepcopy(added)

    def update(
        self,
        taxon_id: str,
        patch: dict,
        *,
        strict: bool = True,
        replace: bool = False,
    ) -> dict:
        """
        Update an existing taxon.
        - patch: partial fields (deep-merged) unless replace=True
        - replace: treat patch as full replacement body (must include required fields)
        """
        tid = taxon_id.strip().upper()
        self.load()
        master = deepcopy(self._master)
        taxa = list(master.get("taxa") or [])
        idx = next((i for i, t in enumerate(taxa) if t.get("id") == tid), None)
        if idx is None:
            raise NotFoundError(f"لا يوجد صنف بالمعرّف: {tid}")

        current = taxa[idx]
        if replace:
            # allow id omission → keep current id
            body = deepcopy(patch)
            body.setdefault("id", tid)
            updated = normalize_taxon(body, strict=strict)
        else:
            merged = deep_merge(current, patch)
            # id change support
            if "id" in patch:
                merged["id"] = str(patch["id"]).strip().upper()
            updated = normalize_taxon(merged, strict=strict)

        # uniqueness if id or scientific_name changed
        new_id = updated["id"]
        new_sci = updated["scientific_name"]
        for i, t in enumerate(taxa):
            if i == idx:
                continue
            if t.get("id") == new_id:
                raise DuplicateError(f"معرّف مكرر: {new_id}")
            if (t.get("scientific_name") or "").casefold() == new_sci.casefold():
                raise DuplicateError(f"اسم علمي مكرر: {new_sci}")

        taxa[idx] = updated
        master["taxa"] = taxa
        self._commit(master, action="update", taxon_id=f"{tid}->{new_id}")
        return deepcopy(updated)

    def delete(self, taxon_id: str) -> dict:
        """Delete a taxon by id and sync all files. Returns the removed taxon."""
        tid = taxon_id.strip().upper()
        self.load()
        master = deepcopy(self._master)
        taxa = list(master.get("taxa") or [])
        idx = next((i for i, t in enumerate(taxa) if t.get("id") == tid), None)
        if idx is None:
            raise NotFoundError(f"لا يوجد صنف بالمعرّف: {tid}")
        removed = taxa.pop(idx)
        master["taxa"] = taxa
        self._commit(master, action="delete", taxon_id=tid)
        return deepcopy(removed)

    def delete_many(self, ids: Iterable[str]) -> list[dict]:
        id_set = {i.strip().upper() for i in ids}
        self.load()
        master = deepcopy(self._master)
        taxa = list(master.get("taxa") or [])
        removed: list[dict] = []
        kept: list[dict] = []
        for t in taxa:
            if t.get("id") in id_set:
                removed.append(t)
            else:
                kept.append(t)
        missing = id_set - {t["id"] for t in removed}
        if missing:
            raise NotFoundError(f"معرّفات غير موجودة: {', '.join(sorted(missing))}")
        master["taxa"] = kept
        self._commit(
            master,
            action="delete_many",
            taxon_id=",".join(sorted(t["id"] for t in removed)),
        )
        return deepcopy(removed)

    def rebuild(self) -> dict[str, Any]:
        """Force rewrite of master + all derived files without data changes."""
        self.load(force=True)
        return self._commit(deepcopy(self._master), action="rebuild", taxon_id="-")

    # ------------------------------------------------------------------ helpers
    def _assert_unique(self, tid: str, scientific_name: str) -> None:
        for t in self.taxa:
            if t.get("id") == tid:
                raise DuplicateError(f"معرّف مكرر: {tid}")
            if (t.get("scientific_name") or "").casefold() == scientific_name.casefold():
                raise DuplicateError(f"اسم علمي مكرر: {scientific_name}")

    def _backup_master(self) -> Path | None:
        if not MASTER_PATH.exists():
            return None
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = ARCHIVE_DIR / f"woody_flora.backup_{stamp}.json"
        shutil.copy2(MASTER_PATH, dest)
        # keep only last 20 backups
        backups = sorted(ARCHIVE_DIR.glob("woody_flora.backup_*.json"))
        for old in backups[:-20]:
            try:
                old.unlink()
            except OSError:
                pass
        return dest

    def _commit(self, master: dict, *, action: str, taxon_id: str) -> dict[str, Any]:
        if self.auto_backup and action != "rebuild":
            self._backup_master()
        summary = rebuild_all(master, write_root_mirror=True)
        self._master = load_master()
        self._append_changelog(action=action, taxon_id=taxon_id, summary=summary)
        return summary

    def _append_changelog(
        self, *, action: str, taxon_id: str, summary: dict
    ) -> None:
        log_path = PROJECT_ROOT / "data" / "changelog.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "taxon_id": taxon_id,
            "taxa_count": summary.get("taxa"),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ factory helpers
    @staticmethod
    def suggest_id(family: str, genus: str, scientific_name: str) -> str:
        return suggest_id(family, genus, scientific_name)

    @staticmethod
    def load_taxon_file(path: str | Path) -> dict:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "taxa" in data and isinstance(data["taxa"], list):
            if len(data["taxa"]) != 1:
                raise ValidationError(
                    "ملف يحتوي عدة taxa — استخدم add_many أو مرّر مدخلاً واحداً"
                )
            return data["taxa"][0]
        if isinstance(data, dict) and "scientific_name" in data:
            return data
        raise ValidationError("صيغة ملف غير معروفة — توقّع كائن صنف أو {taxa:[...]}")

    def apply(self, mutator: Callable[[list[dict]], list[dict]]) -> dict[str, Any]:
        """
        Advanced: apply a pure function to the taxa list, then rebuild.
        mutator(taxa) -> new_taxa
        """
        self.load()
        master = deepcopy(self._master)
        new_taxa = mutator(list(master.get("taxa") or []))
        if not isinstance(new_taxa, list):
            raise ValidationError("mutator يجب أن يُرجع قائمة taxa")
        # re-normalize all for safety
        normalized = [normalize_taxon(t, strict=True) for t in new_taxa]
        # unique check
        ids = [t["id"] for t in normalized]
        if len(ids) != len(set(ids)):
            raise DuplicateError("قائمة الناتج تحتوي معرّفات مكررة")
        sci = [t["scientific_name"].casefold() for t in normalized]
        if len(sci) != len(set(sci)):
            raise DuplicateError("قائمة الناتج تحتوي أسماء علمية مكررة")
        master["taxa"] = normalized
        return self._commit(master, action="apply", taxon_id="*")
