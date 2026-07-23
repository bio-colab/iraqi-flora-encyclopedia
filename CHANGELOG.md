# Changelog

## v0.4.0 — PHP/Hostinger runtime conversion

- حُوّل مسار التشغيل الرئيسي من Python المحلي إلى Backend كامل بـ PHP عبر `api/index.php`.
- أضيف توجيه Apache/Hostinger عبر `.htaccess` لمسارات `/api/*`.
- أضيف `router.php` للتطوير المحلي باستخدام `php -S 127.0.0.1:8765 router.php`.
- أضيفت إعادة تنفيذ PHP لوظائف البيانات الأساسية: health, stats, enums, meta, search, list/get taxa, CRUD للأصناف، suggest-id، الصلاحيات، الجلسات، أكواد المدراء، طلبات التغيير، وسجل النشاط.
- أضيفت إعادة بناء ملفات JSON المشتقة من PHP: master mirror, by_habit, by_category, by_family, by_nativity, reference, index.
- أضيف `tools/php_smoke_test.php` لاختبار توافق REST API الجديد مع الواجهة ومسارات Hostinger.
- حُدّث README لتوثيق أن التشغيل الإنتاجي أصبح PHP ومتوافقاً مع Hostinger، وأن ملفات Python المتبقية أدوات مساندة/أرشيفية فقط.


All notable changes to the **Iraqi Flora Encyclopedia** (موسوعة الفلورا العراقية) are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),  
and this project aims to follow [Semantic Versioning](https://semver.org/) for schema and tooling releases.

Automated operation logs (add / update / delete) are also appended to `data/changelog.jsonl`.

---

## [Unreleased]

### Planned
- Deeper reconciliation against *Flora of Iraq* volumes
- Expansion of herbaceous and grass coverage beyond seed records
- Optional CSV/Excel import-export
- Optional PHP/MySQL backend for Hostinger Premium shared hosting (deferred; Python retained)

---

## [0.3.1] — 2026-07-23

### Fixed
- **Frontend plan phase 1 (UI polish / bug audit)** against `plan.md`:
  - Modal open state confirmed unified on `.open` (JS + CSS)
  - Toast styles: richer success/error backgrounds; added **`.toast.info`**
  - Header stats (`#statTotal`, `#statNative`, `#statFamilies`) null-safe updates
  - Table/cards use consistent badge classes (`data-table`, `id-badge`, `family-tag`, `zone-pill`, native/habit/status)
  - Add/edit form already includes zones, presence, local status, IUCN, notes; default presence remains **`موجود`**
- Smoke-tested local API: `/api/health`, `/api/stats`, `/api/taxa` respond OK under `web_server.py`

### Changed
- `plan.md` marked **Phase 1 complete**; **PHP migration deferred** — keep Python CLI + `web_server.py` for academic beta (local or VPS)
- README deployment notes: Hostinger shared vs Python/VPS path clarified

### Tooling
- No backend stack change (stdlib Python only)

---

## [0.3.0] — 2026-07-21

### Added
- **Schema-aware search engine** (`tools/flora_lib/search.py`):
  - Free-text over schema paths (id, scientific name, Arabic/Kurdish/English names, notes, classification, zones, IUCN, …)
  - Structured filters: habit, family, genus, order, zone, native, endemic, presence, local status, IUCN, category group, flagship
  - Pagination metadata (`total` / `offset` / `limit`) and sort options
- **Local web frontend** (`frontend/`):
  - Full **CRUD** UI (create / read / update / delete) writing through `FloraManager` with validation and fan-out rebuild
  - Dynamic view modes: **Table / Cards / Grid**
  - Sidebar filters aligned with dataset structure (category group, habit, family, zone, nativity, …)
  - Arabic RTL interface with taxon detail modal and form editor
- **HTTP API + static server** (`tools/web_server.py`, stdlib only):
  - `GET /api/taxa`, `GET /api/taxa/{id}`, `POST /api/taxa`, `PUT|PATCH /api/taxa/{id}`, `DELETE /api/taxa/{id}`
  - `GET /api/stats`, `/api/enums`, `/api/meta`, `/api/health`
  - `POST /api/suggest-id`, `POST /api/search`
- **Launcher:** `file.bat` — double-click to start the frontend on `http://127.0.0.1:8765/`

### Changed
- `FloraManager.search` / new `search_detailed` use the schema-aware engine
- CLI `search` accepts optional query plus filters (`--genus`, `--zone`, `--presence`, `--local-status`, `--id`, `--category`, `--offset`, `--meta`)
- `flora_lib` package version **1.0.0 → 1.1.0**

### Tooling
- No third-party web dependencies (Python standard library `ThreadingHTTPServer` only)

---

## [0.2.0] — 2026-07-21

### Added
- **Web-research expansion batch (+36 taxa)** from open encyclopedic sources:
  - Wikipedia *Category:Flora of Iraq*
  - Wikipedia *Zagros Mountains forest steppe*
  - Wikipedia *Mesopotamian Marshes* / *Mesopotamian shrub desert*
  - Supporting species pages (e.g. *Quercus brantii*, POWO / Trees and Shrubs Online ranges)
- High-value woody gaps filled, including among others:
  - *Quercus brantii*, *Quercus boissieri*
  - *Celtis tournefortii*, *Celtis caucasica*
  - Multiple *Prunus* / almond-group taxa (*microcarpa*, *argentea*, *brachypetala*, *carduchorum*, *scoparia*)
  - *Cotoneaster nummularius*, *Lonicera nummulariifolia*
  - *Vitex agnus-castus*, *Anagyris foetida*, *Fraxinus angustifolia*
  - *Rosa phoenicia*, *Rosa boissieri*, *Rhamnus petiolaris*
  - *Populus nigra*, *Tamarix meyeri*, *Haloxylon scoparium*, *Astragalus brachycalyx*, *Rheum ribes*
- **New growth-form (habit) categories** for non-woody flora:
  - `عشبة_معمّرة` (perennial herbs)
  - `عشبة_حولية` (annual herbs)
  - `نجيلة_أو_عشب` (grasses / grass-like)
  - `مائي` (aquatic / marsh)
- Seed non-woody records for marshes and steppe desert:
  - *Phragmites australis*, *Typha domingensis*, *Cyperus papyrus*
  - *Stipagrostis plumosa*
  - *Papaver rhoeas*, *Iris persica*, *Allium iranicum*, *Teucrium polium*, *Thymbra spicata*, …
- Derived files for new habits/categories:
  - `data/by_habit/{perennial_herbs,annual_herbs,grasses,aquatic}.json`
  - `data/by_category/{05_herbs,06_grasses,07_aquatic}.json`
- Batch source file: `tools/examples/batch_web_research_additions.json`
- Report: `data/web_research_additions_report.json`

### Changed
- Dataset size: **116 → 152** taxa
- Families: **45 → 51**
- Native count: **105 → 141** (non-native unchanged at 11)
- Schema / field catalog habit enums expanded to include non-woody forms
- Category rebuild no longer emits empty herb/grass placeholders only — real groups are generated

### Tooling
- `flora_lib.config` and rebuild pipeline updated for new habits and category groups
- `python tools/manage_flora.py add-many` used for atomic multi-record import with full fan-out sync

---

## [0.1.0] — 2026-07-21

### Added
- Initial structured dataset of **Iraqi woody flora** (trees, shrubs, subshrubs, woody climbers)
- Unified **JSON Schema** for plant taxon entries (`schema/plant_taxon.schema.json`)
- Field catalog (`schema/field_catalog.json`) with controlled vocabularies for:
  - `habit`, `presence_in_iraq`, `iraq_local_status`, `confidence`, zones
- Master dataset layout:
  - `data/master/woody_flora.json` (source of truth)
  - Root mirror `iraq_woody_flora.json`
- Split views:
  - by habit, category group, family, nativity
  - vegetation zones + analysis under `data/reference/`
  - `data/index.json` totals and file map
- **Flora management system** (`tools/flora_lib` + `tools/manage_flora.py`):
  - `add` / `add-many` / `update` / `delete` / `search` / `list` / `get` / `stats` / `rebuild` / `export` / `enums`
  - Automatic rebuild of all derived files after every mutation
  - Validation + normalization (IDs, enums, IUCN placeholders, names)
  - Optional master backups under `archive/`
  - Operation log `data/changelog.jsonl`
- Cleaning pipeline artifacts:
  - Original scrape archived as `archive/iraq_woody_flora.raw.json`
  - `data/cleaning_report.json`
- Example taxon template: `tools/examples/taxon_template.json`

### Fixed / Normalized (initial clean)
- Meta `taxa_count` corrected to match actual records (was under-declared)
- Non-standard IUCN placeholder `مُقيَّم` normalized to `category: null` + `assessment_noted` when applicable
- Parenthetical family annotations folded into `taxonomic_note`; family field kept clean
- Non-native taxa ensured to carry `introduction_status`
- Local-status vocabulary extended for cultivated / invasive cases
- Stable key order; taxa sorted by family → genus → scientific name

### Dataset snapshot at 0.1.0
- **116** taxa (105 native, 11 non-native)
- **45** families
- **7** vegetation zones
- Habits (woody only at this stage): tree, small tree, shrub, spiny shrub, saline shrub, subshrub, woody climber

---

## Versioning notes

| Component | Versioning intent |
|-----------|-------------------|
| Data content | Minor bumps when taxa or fields expand without breaking consumers |
| Schema (`$schema_version`) | Currently **1.1**; major if required fields/enums break compatibility |
| Tooling (`flora_lib`) | Documented here; API may evolve with care |

---

## Credits

- **Volunteer author:** Elias Sharar (إلياس شرار)
- **Organization / GitHub home:** [bio-colab](https://github.com/bio-colab)
- Sources consulted during compilation include secondary literature and open encyclopedic pages (Wikipedia ecoregions & flora categories, restoration project notes, IUCN-related disclosures where verified). Full epistemic notes remain inside dataset `meta` / `analysis` sections.

---

[Unreleased]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bio-colab/iraqi-flora-encyclopedia/releases/tag/v0.1.0
