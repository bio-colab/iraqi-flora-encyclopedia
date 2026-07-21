#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نقطة الدخول لإدارة أصناف موسوعة الفلورا العراقية.

الاستخدام من جذر المشروع:
  python tools/manage_flora.py --help
  python tools/manage_flora.py stats
  python tools/manage_flora.py list
  python tools/manage_flora.py get FAG-QUE-AEG
  python tools/manage_flora.py search بلوط
  python tools/manage_flora.py add --file path/to/taxon.json
  python tools/manage_flora.py update ID --set notes="..."
  python tools/manage_flora.py delete ID --yes
  python tools/manage_flora.py rebuild

أو برمجياً:
  from flora_lib import FloraManager
  m = FloraManager()
  m.add({...})
  m.update("FAG-QUE-AEG", {"notes": "..."})
  m.delete("DEMO-XXX-001")
"""

from __future__ import annotations

import sys
from pathlib import Path

# tools/ on sys.path so `import flora_lib` works
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from flora_lib.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
