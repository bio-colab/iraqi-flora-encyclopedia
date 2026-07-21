# Changelog

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
- Arabic-first web browse UI (future)

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

[Unreleased]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/bio-colab/iraqi-flora-encyclopedia/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bio-colab/iraqi-flora-encyclopedia/releases/tag/v0.1.0
