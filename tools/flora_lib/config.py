# -*- coding: utf-8 -*-
"""Paths, enums, and category maps for the Iraqi Flora Encyclopedia."""

from __future__ import annotations

from pathlib import Path

# tools/flora_lib/config.py → project root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
MASTER_PATH = DATA_DIR / "master" / "woody_flora.json"
ROOT_MASTER_PATH = PROJECT_ROOT / "iraq_woody_flora.json"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
SCHEMA_DIR = PROJECT_ROOT / "schema"
BY_HABIT_DIR = DATA_DIR / "by_habit"
BY_CATEGORY_DIR = DATA_DIR / "by_category"
BY_NATIVITY_DIR = DATA_DIR / "by_nativity"
BY_FAMILY_DIR = DATA_DIR / "by_family"
REF_DIR = DATA_DIR / "reference"
INDEX_PATH = DATA_DIR / "index.json"

SCHEMA_VERSION = "1.1"

HABIT_FILES = {
    "شجرة": {
        "file": "trees",
        "label_ar": "أشجار",
        "label_en": "Trees",
        "category_group": "tree",
    },
    "شجرة_صغيرة": {
        "file": "small_trees",
        "label_ar": "أشجار صغيرة",
        "label_en": "Small Trees",
        "category_group": "tree",
    },
    "شجيرة": {
        "file": "shrubs",
        "label_ar": "شجيرات",
        "label_en": "Shrubs",
        "category_group": "shrub",
    },
    "شجيرة_شوكية": {
        "file": "spiny_shrubs",
        "label_ar": "شجيرات شوكية",
        "label_en": "Spiny Shrubs",
        "category_group": "shrub",
    },
    "شجيرة_ملحية": {
        "file": "saline_shrubs",
        "label_ar": "شجيرات ملحية",
        "label_en": "Saline Shrubs",
        "category_group": "shrub",
    },
    "شبه_شجيرة": {
        "file": "subshrubs",
        "label_ar": "شبه شجيرات",
        "label_en": "Subshrubs",
        "category_group": "subshrub",
    },
    "متسلق_خشبي": {
        "file": "woody_climbers",
        "label_ar": "متسلقات خشبية",
        "label_en": "Woody Climbers",
        "category_group": "climber",
    },
    # Non-woody categories (phase 2 expansion from encyclopedic sources)
    "عشبة_معمّرة": {
        "file": "perennial_herbs",
        "label_ar": "أعشاب معمّرة",
        "label_en": "Perennial Herbs",
        "category_group": "herb",
    },
    "عشبة_حولية": {
        "file": "annual_herbs",
        "label_ar": "أعشاب حولية",
        "label_en": "Annual Herbs",
        "category_group": "herb",
    },
    "نجيلة_أو_عشب": {
        "file": "grasses",
        "label_ar": "نجيليات وأعشاب",
        "label_en": "Grasses and Grass-like",
        "category_group": "grass",
    },
    "مائي": {
        "file": "aquatic",
        "label_ar": "نباتات مائية وأهوار",
        "label_en": "Aquatic / Marsh Plants",
        "category_group": "aquatic",
    },
}

CATEGORY_GROUPS = {
    "trees": {
        "habits": ["شجرة", "شجرة_صغيرة"],
        "label_ar": "الأشجار (بما فيها الصغيرة)",
        "label_en": "Trees (including small trees)",
        "file": "01_trees",
    },
    "shrubs": {
        "habits": ["شجيرة", "شجيرة_شوكية", "شجيرة_ملحية"],
        "label_ar": "الشجيرات (عادية / شوكية / ملحية)",
        "label_en": "Shrubs (common / spiny / saline)",
        "file": "02_shrubs",
    },
    "subshrubs": {
        "habits": ["شبه_شجيرة"],
        "label_ar": "شبه الشجيرات",
        "label_en": "Subshrubs",
        "file": "03_subshrubs",
    },
    "woody_climbers": {
        "habits": ["متسلق_خشبي"],
        "label_ar": "المتسلقات الخشبية",
        "label_en": "Woody Climbers",
        "file": "04_woody_climbers",
    },
    "herbs": {
        "habits": ["عشبة_معمّرة", "عشبة_حولية"],
        "label_ar": "الأعشاب (حولية ومعمّرة)",
        "label_en": "Herbs (annual and perennial)",
        "file": "05_herbs",
    },
    "grasses": {
        "habits": ["نجيلة_أو_عشب"],
        "label_ar": "النجيليات وما شابهها",
        "label_en": "Grasses and grass-like plants",
        "file": "06_grasses",
    },
    "aquatic": {
        "habits": ["مائي"],
        "label_ar": "نباتات الأهوار والمائية",
        "label_en": "Marsh and aquatic plants",
        "file": "07_aquatic",
    },
}

# No longer empty placeholders — real category groups above cover herbs/grasses
PLACEHOLDER_CATEGORIES: list[tuple[str, str, str]] = []

ALLOWED_PRESENCE = [
    "موجود",
    "موجود_نادر_محلياً",
    "مشكوك_في_أصالته",
    "غير_مؤكد_الوجود",
]

ALLOWED_LOCAL_STATUS = [
    "مستقر_نسبياً",
    "متراجع",
    "متراجع_بشدة",
    "نادر_محلياً",
    "مهدد_محلياً",
    "غير_معروف",
    "مزروع",
    "مزروع_تجريبياً",
    "مزروع_واسعاً",
    "مزروع_واسعاً_ومتراجع",
    "غازٍ_متوسع",
]

ALLOWED_CONFIDENCE = ["عالية", "متوسطة", "منخفضة"]

ALLOWED_HABIT = list(HABIT_FILES.keys())

ALLOWED_ZONES = [
    "DESERT",
    "STEPPE",
    "MOUNTAIN_FOREST",
    "THORN_CUSHION_ALPINE",
    "RIVERINE",
    "MARSH_SALINE",
    "COASTAL",
]

IUCN_CODES = {"LC", "NT", "VU", "EN", "CR", "EW", "EX", "DD", "NE"}

STANDARD_TAXON_KEYS = [
    "id",
    "scientific_name",
    "taxonomic_note",
    "classification",
    "names",
    "habit",
    "zones",
    "native_to_iraq",
    "endemic_to_iraq",
    "presence_in_iraq",
    "introduction_status",
    "iucn",
    "iraq_local_status",
    "flag",
    "flagship_case",
    "notes",
]

ID_PATTERN = r"^[A-Z]{3}-[A-Z]{3}-[A-Z0-9]{2,4}$"
