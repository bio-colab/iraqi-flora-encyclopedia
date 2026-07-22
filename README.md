# موسوعة الفلورا العراقية  
# Iraqi Flora Encyclopedia

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Data: JSON](https://img.shields.io/badge/data-JSON-blue.svg)](#هيكل-البيانات--data-layout)
[![Python 3](https://img.shields.io/badge/python-3.10%2B-yellow.svg)](#إدارة-البيانات--data-management)
[![Org: bio-colab](https://img.shields.io/badge/org-bio--colab-2ea44f.svg)](https://github.com/bio-colab)

مجموعة بيانات مفتوحة ومنظمة لنباتات العراق، مع مخطط موحّد وأدوات بايثون لإدارة الأصناف (إضافة / تعديل / حذف) ومزامنة كل الملفات المشتقة تلقائياً.

> **مشروع تطوعي** من إعداد **Elias Sharar** (إلياس شرار)، ويُنشر تحت مظلة **[bio-colab](https://github.com/bio-colab)** لأغراض المعرفة المفتوحة، التعليم، والحفظ البيئي — بلا أهداف ربحية.

---

## English summary

Open, structured plant data for **Iraq**, with a unified JSON schema and a Python management CLI that keeps the master dataset and all derived category files in sync.

This is a **volunteer project by Elias Sharar**, published under the **[bio-colab](https://github.com/bio-colab)** organization for open science, education, and conservation.

| Metric | Value |
|--------|------:|
| Taxa (records) | **152** |
| Native to Iraq | **141** |
| Non-native (contrast / cultivated / invasive) | **11** |
| Families | **51** |
| Vegetation zones | **7** |
| Schema version | **1.1** |

---

## لماذا هذا المشروع؟

- توثيق الفلورا العراقية بصيغة قابلة للقراءة آلياً (machine-readable).
- فصل **الحالة العالمية (IUCN)** عن **الوضع المحلي داخل العراق** — مفارقة شائعة في أشجار كردستان.
- توفير نقطة انطلاق للباحثين، المعلّمين، مبادرات التحريج، وتطبيقات التنوع الحيوي.
- إدارة مركزية: تعديل واحد → تحديث كل التصنيفات (habit / category / family / nativity).

> **تنويه:** البيانات غير حاصرة. يمكن للملف أن **يثبت** وجود نوع مذكور فيه، ولا يمكنه **نفي** وجود نوع غير مذكور. المرجع الحاكم للأسماء والتوزيع يبقى *Flora of Iraq* والأدبيات المتخصصة.

---

## هيكل المستودع

```text
.
├── README.md
├── CHANGELOG.md
├── file.bat                       # تشغيل الواجهة (Windows)
├── iraq_woody_flora.json          # نسخة رئيسية مريحة في الجذر (مرآة)
├── frontend/                      # واجهة ويب تفاعلية (CRUD + بحث)
├── data/
│   ├── master/woody_flora.json    # المصدر المعتمد (source of truth)
│   ├── index.json                 # فهرس سريع + إحصاءات
│   ├── by_habit/                  # حسب شكل النمو
│   ├── by_category/               # مجموعات أوسع (أشجار، شجيرات، أعشاب…)
│   ├── by_family/                 # حسب العائلة النباتية
│   ├── by_nativity/               # أصيل / غير أصيل
│   ├── reference/                 # مناطق نباتية + تحليلات + meta
│   └── changelog.jsonl            # سجل عمليات الإدارة الآلي
├── schema/
│   ├── plant_taxon.schema.json
│   ├── woody_flora_dataset.schema.json
│   └── field_catalog.json
├── tools/
│   ├── manage_flora.py            # واجهة سطر الأوامر
│   ├── web_server.py              # خادم الواجهة + REST API
│   ├── flora_lib/                 # مكتبة الإدارة + محرك البحث
│   └── examples/                  # قوالب وإضافات جماعية
└── archive/                       # نسخ خام / احتياطية
```

---

## هيكل البيانات / Data layout

### مصدر الحقيقة
- **`data/master/woody_flora.json`** — الملف الرئيسي.
- **`iraq_woody_flora.json`** — مرآة للجذر (نفس المحتوى بعد كل عملية مزامنة).

### التصنيفات المشتقة
| المجلد | الوصف |
|--------|--------|
| `data/by_habit/` | أشجار، أشجار صغيرة، شجيرات، شوكية، ملحية، شبه شجيرات، متسلقات، أعشاب، نجيليات، مائي |
| `data/by_category/` | مجموعات مجمّعة (`01_trees` … `07_aquatic`) |
| `data/by_family/` | ملف لكل عائلة (مثل `Fagaceae.json`) |
| `data/by_nativity/` | `native.json` / `non_native.json` |
| `data/reference/` | المناطق النباتية، التحليلات، البيانات الوصفية |

### حقول المدخل (مختصر)
| Field | Description |
|-------|-------------|
| `id` | رمز ثابت مثل `FAG-QUE-AEG` |
| `scientific_name` | الاسم العلمي + السلطة عند التوفر |
| `classification` | order / family / genus (+ اختياري) |
| `names` | عربي (بثقة)، كردي اختياري، إنجليزي |
| `habit` | شكل النمو (تعداد موحّد) |
| `zones` | مناطق نباتية: `DESERT`, `STEPPE`, `MOUNTAIN_FOREST`, … |
| `native_to_iraq` | boolean |
| `presence_in_iraq` | موجود / نادر / مشكوك… |
| `iucn` | رتبة IUCN + `verified_in_session` |
| `iraq_local_status` | تقدير محلي نوعي |
| `notes` | ملاحظات بيئية وحفظية |

المخطط الكامل: [`schema/plant_taxon.schema.json`](schema/plant_taxon.schema.json)  
كتالوج الحقول: [`schema/field_catalog.json`](schema/field_catalog.json)

---

## المناطق النباتية (7)

1. **DESERT** — الصحراء  
2. **STEPPE** — السهوب / شبه الصحراء  
3. **MOUNTAIN_FOREST** — غابات الجبال (البلوط)  
4. **THORN_CUSHION_ALPINE** — الشوك الوسادي وما فوق خط الشجر  
5. **RIVERINE** — الأودية وضفاف الأنهار  
6. **MARSH_SALINE** — الأهوار والسبخات  
7. **COASTAL** — الساحل (بدون أشجار بحرية أصيلة موثّقة)

التفاصيل: [`data/reference/vegetation_zones.json`](data/reference/vegetation_zones.json)

---

## الواجهة الرسومية / Web UI

واجهة عربية (RTL) للبحث وعرض وإدارة الأصناف (إنشاء / قراءة / تعديل / حذف)، مع أوضاع عرض **جدول / بطاقات / شبكة** وتصفية حسب حقول المخطط.

### التشغيل السريع (Windows)

انقر نقراً مزدوجاً على **`file.bat`** — يفتح المتصفح على `http://127.0.0.1:8765/`.

أو من الطرفية:

```bash
python tools/web_server.py
# أو بدون فتح المتصفح:
python tools/web_server.py --no-browser --port 8765
```

يتطلب **Python 3.10+** فقط (بدون Flask أو حزم خارجية). التعديلات تُحفظ عبر `FloraManager` مع إعادة بناء كل الملفات المشتقة تلقائياً.

### تسجيل الدخول والصلاحيات

| الدور | من هم | الصلاحيات |
|--------|--------|-----------|
| **ضيف** | بلا حساب | عرض وبحث فقط |
| **مستخدم** | دخول عبر Google | طلب إضافة / تعديل / حذف (مراجعة مدير) |
| **مدير** | ترقية بكود من المالك | CRUD مباشر + مراجعة الطلبات + سجل النشاط |
| **المالك** | `aliasbio95@gmail.com` فقط | كل صلاحيات المدير + توليد/إلغاء أكواد الترقية + إزالة المدراء |

**تفعيل Google OAuth**

1. أنشئ OAuth Client (Web) في [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. أضف Redirect URI: `http://127.0.0.1:8765/api/auth/google/callback`
3. انسخ [`auth_config.example.json`](auth_config.example.json) → `auth_config.json` واملأ:
   - `google_client_id`
   - `google_client_secret`
4. أعد تشغيل `python tools/web_server.py`

يمكن أيضاً استخدام متغيرات البيئة `GOOGLE_CLIENT_ID` و `GOOGLE_CLIENT_SECRET`.

للتجربة المحلية بدون Google: في `data/auth/config.json` اضبط `"allow_dev_login": true` (مفعّل افتراضياً للتطوير؛ عطّله في الإنتاج).

**مسار الترقية إلى مدير:** المالك → لوحة الإدارة → «أكواد الترقية» → توليد كود لمرة واحدة (صالح 48 ساعة) → يرسله للمستخدم → المستخدم يدخل الكود من «كود ترقية».

بيانات الجلسات والمستخدمين تُحفظ تحت `data/auth/` (لا ترفع `secret.key` أو `auth_config.json` إلى Git).

---

## إدارة البيانات / Data management

يتطلب **Python 3.10+** (مكتبة قياسية فقط — بدون تبعيات خارجية).

### أوامر شائعة

```bash
# إحصاءات
python tools/manage_flora.py stats

# قائمة / بحث / عرض
python tools/manage_flora.py list --habit شجرة
python tools/manage_flora.py search بلوط
python tools/manage_flora.py search --family Fagaceae --zone MOUNTAIN_FOREST
python tools/manage_flora.py search --category trees --native true --json --meta
python tools/manage_flora.py get FAG-QUE-AEG

# إضافة صنف من ملف JSON
python tools/manage_flora.py add --file tools/examples/taxon_template.json

# إضافة دفعة
python tools/manage_flora.py add-many --file tools/examples/batch_web_research_additions.json

# تعديل
python tools/manage_flora.py update FAG-QUE-AEG --set iraq_local_status=متراجع
python tools/manage_flora.py update FAG-QUE-AEG --set notes="نص محدّث"

# حذف
python tools/manage_flora.py delete SOME-ID-001 --yes

# إعادة بناء كل الملفات من الـ master
python tools/manage_flora.py rebuild

# القيم المسموحة
python tools/manage_flora.py enums
```

### استخدام برمجي

```python
import sys
sys.path.insert(0, "tools")

from flora_lib import FloraManager

m = FloraManager()  # نسخ احتياطي تلقائي عند التعديل

m.add({ ... })                              # إضافة
m.update("FAG-QUE-AEG", {"notes": "..."})   # تعديل
m.delete("DEMO-XXX-001")                    # حذف
hits = m.search("بلوط", habit="شجرة")       # بحث
```

بعد كل عملية ناجحة يُعاد توليد:
- master + مرآة الجذر  
- by_habit / by_category / by_family / by_nativity  
- reference + index  
- سجل في `data/changelog.jsonl`  
- نسخة احتياطية في `archive/` (عند التعديل)

---

## المساهمة

هذا مشروع **تطوعي مفتوح**. نرحّب بـ:

1. اقتراح أنواع ناقصة (يفضّل مع مرجع).
2. تصحيح الأسماء المحلية (عربي / كردي) مع درجة ثقة.
3. التحقق من رتب IUCN (`verified_in_session`).
4. تحسين التوثيق والترجمة.
5. تقارير أخطاء عبر GitHub Issues على حساب **bio-colab**.

### خطوات مقترحة
1. Fork المستودع.
2. أضف/عدّل عبر `tools/manage_flora.py` (لا تحرّر الملفات المشتقة يدوياً).
3. افتح Pull Request مع وصف واضح للمصادر.

قالب صنف جديد: [`tools/examples/taxon_template.json`](tools/examples/taxon_template.json)

---

## الترخيص والترقيم

- **البيانات والنصوص التوثيقية في هذا المستودع:**  
  [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)  
  يُرجى نسب العمل إلى:  
  **Elias Sharar / bio-colab — Iraqi Flora Encyclopedia (موسوعة الفلورا العراقية)**.

- **الشفرة في `tools/`:** نفس نسب الإسناد؛ يمكن معاملتها عملياً كشيفرة مفتوحة للاستخدام العلمي والتعليمي مع الإبقاء على الإسناد.

- الأسماء العلمية والتقييمات العالمية (IUCN وغيرها) تبقى خاضعة لمصادرها الأصلية.

---

## الإسناد / Citation

```text
Sharar, E. (2026). Iraqi Flora Encyclopedia (موسوعة الفلورا العراقية) [Data set].
bio-colab. https://github.com/bio-colab/<repo-name>
```

```bibtex
@misc{sharar_iraqi_flora_2026,
  author       = {Sharar, Elias},
  title        = {Iraqi Flora Encyclopedia},
  year         = {2026},
  howpublished = {bio-colab},
  note         = {Volunteer open dataset of Iraqi plant taxa},
  url          = {https://github.com/bio-colab/<repo-name>}
}
```

> استبدل `<repo-name>` باسم المستودع الفعلي بعد الرفع.

---

## تنويهات علمية

- القائمة **غير مكتملة**؛ الفلورا الوعائية العراقية تُقدَّر بالآلاف.
- حقل `iraq_local_status` **تقديري نوعي** — لا توجد قائمة حمراء نباتية وطنية رسمية معتمدة شاملة حتى تاريخ التجميع.
- بعض الأنواع مُدرجة بصيغة تجميعية (مثل `Astragalus spp.`) ريثما تُفكك إلى أنواع.
- الأنواع غير الأصيلة (`native_to_iraq: false`) أُدرجت للتمييز أو التحذير (مزروع / غازٍ)، وليست إثباتاً للأصالة.

---

## الفريق والملكية

| | |
|--|--|
| **المبادرة** | مشروع تطوعي |
| **المعدّ** | **Elias Sharar** (إلياس شرار) |
| **المنظمة / الحساب** | [**bio-colab**](https://github.com/bio-colab) |
| **الهدف** | معرفة مفتوحة + دعم الحفظ البيئي في العراق |

شكراً لكل من يساهم في توثيق وحماية التنوع النباتي العراقي.

---

## روابط سريعة

- الفهرس: [`data/index.json`](data/index.json)
- السجل النصي: [`CHANGELOG.md`](CHANGELOG.md)
- سجل العمليات الآلي: [`data/changelog.jsonl`](data/changelog.jsonl)
- المخطط: [`schema/`](schema/)
- الأداة: [`tools/manage_flora.py`](tools/manage_flora.py)
- الواجهة: [`file.bat`](file.bat) / [`tools/web_server.py`](tools/web_server.py) / [`frontend/`](frontend/)
