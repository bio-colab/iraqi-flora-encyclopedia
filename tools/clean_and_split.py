#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline قديم (مرحلة التنظيف الأولى) — يُعاد توجيهه الآن إلى FloraManager.rebuild().

للاستخدام اليومي استخدم:
  python tools/manage_flora.py rebuild
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from flora_lib.manager import FloraManager  # noqa: E402


def main() -> int:
    m = FloraManager(auto_backup=False)
    summary = m.rebuild()
    print("=== Rebuild via FloraManager ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
