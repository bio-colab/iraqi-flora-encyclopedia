# موسوعة الفلورا العراقية  
# Iraqi Flora Encyclopedia

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Data: JSON](https://img.shields.io/badge/data-JSON-blue.svg)](#هيكل-البيانات--data-layout)
[![PHP 8](https://img.shields.io/badge/PHP-8.1%2B-777BB4.svg)](#إدارة-البيانات--data-management)
[![Org: bio-colab](https://img.shields.io/badge/org-bio--colab-2ea44f.svg)](https://github.com/bio-colab)

مجموعة بيانات مفتوحة ومنظمة لنباتات العراق، مع مخطط موحّد وواجهة/REST API مكتوبة بـ PHP لإدارة الأصناف (إضافة / تعديل / حذف) ومزامنة كل الملفات المشتقة تلقائياً على استضافات PHP المشتركة مثل Hostinger.

> **مشروع تطوعي** من إعداد **Elias Sharar** (إلياس شرار)، ويُنشر تحت مظلة **[bio-colab](https://github.com/bio-colab)** لأغراض المعرفة المفتوحة، التعليم، والحفظ البيئي — بلا أهداف ربحية.

---

## English summary

Open, structured plant data for **Iraq**, with a unified JSON schema and a PHP REST backend that keeps the master dataset and all derived category files in sync on standard PHP shared hosting.

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
├── file.bat                       # تشغيل الواجهة محلياً عبر PHP (Windows)
├── iraq_woody_flora.json          # نسخة رئيسية مريحة في الجذر (مرآة)
├── api/index.php                  # REST API كامل بـ PHP (Hostinger-ready)
├── .htaccess                      # توجيه Apache/Hostinger لمسارات /api
├── router.php                     # Router للتطوير المحلي عبر php -S
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
│   ├── php_smoke_test.php         # اختبار Smoke للـ PHP API
│   ├── manage_flora.py            # أدوات Python قديمة/مساندة محلية فقط
│   ├── web_server.py              # خادم Python قديم للتطوير فقط
│   ├── flora_lib/                 # مكتبة Python قديمة/مساندة
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

واجهة عربية (RTL) للبحث وعرض وإدارة الأصناف (إنشاء / قراءة / تعديل / حذف)، مع أوضاع عرض **جدول / بطاقات / شبكة** وتصفية حسب حقول المخطط. تعمل الواجهة الآن فوق Backend كامل بـ **PHP** عبر المسارات نفسها `/api/*`.

### التشغيل السريع المحلي بـ PHP

```bash
php -S 127.0.0.1:8765 router.php
```

ثم افتح `http://127.0.0.1:8765/`. لا يحتاج Backend الإنتاج إلى Python؛ واجهة REST تعمل من `api/index.php` وتعيد بناء ملفات JSON المشتقة تلقائياً.

### النشر على Hostinger / Apache PHP

1. ارفع ملفات المشروع كما هي.
2. تأكد أن `api/index.php` و`.htaccess` موجودان في جذر الموقع.
3. اجعل إصدار PHP من لوحة Hostinger حديثاً قدر الإمكان (يفضل PHP 8.1+).
4. اجعل مجلدات `data/` و`archive/` قابلة للكتابة من PHP.
5. افتح `/api/health` للتأكد من أن Backend يعمل.

> تم تحويل مسار التشغيل الرئيسي إلى PHP. ملفات Python المتبقية أدوات مساندة/أرشيفية وليست مطلوبة لتشغيل الموقع على Hostinger. على Windows يمكن تشغيل `file.bat` وسيستخدم PHP لا Python.

### جاهزية البيتا الأكاديمية والاستضافة

الواجهة وواجهة REST جاهزتان لمراجعة المختصين **محلياً** أو على أي بيئة تشغّل PHP 8.1+، بما في ذلك Hostinger/Apache PHP.

| البيئة | الحالة |
|--------|--------|
| محلي PHP | ✅ `php -S 127.0.0.1:8765 router.php` |
| Hostinger Premium **Shared** | ✅ مدعوم عبر `api/index.php` + `.htaccess` |
| Python / VPS | اختياري/قديم — لم يعد مطلوباً للتشغيل |

**قبل الإنتاج / مشاركة رابط عام:**
1. عطّل الدخول التجريبي: في `data/auth/config.json` اضبط `"allow_dev_login": false`.
2. اضبط Google OAuth مع Redirect URI الحقيقي للدومين (وليس فقط `127.0.0.1`).
3. لا ترفع `data/auth/secret.key` ولا `auth_config.json` إلى Git.

تفاصيل خطة الإطلاق والأخطاء المصلحة: [`plan.md`](plan.md) · السجل: [`CHANGELOG.md`](CHANGELOG.md) (**v0.3.1**).

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
4. أعد رفع/تحديث ملفات PHP أو أعد تشغيل خادم PHP المحلي

يمكن أيضاً استخدام متغيرات البيئة `GOOGLE_CLIENT_ID` و `GOOGLE_CLIENT_SECRET`.

للتجربة المحلية بدون Google: في `data/auth/config.json` اضبط `"allow_dev_login": true` (مفعّل افتراضياً للتطوير؛ عطّله في الإنتاج).

**مسار الترقية إلى مدير:** المالك → لوحة الإدارة → «أكواد الترقية» → توليد كود لمرة واحدة (صالح 48 ساعة) → يرسله للمستخدم → المستخدم يدخل الكود من «كود ترقية».

بيانات الجلسات والمستخدمين تُحفظ تحت `data/auth/` (لا ترفع `secret.key` أو `auth_config.json` إلى Git).

---

## إدارة البيانات / Data management

التشغيل الإنتاجي يتطلب **PHP 8.1+** فقط. أدوات Python القديمة اختيارية وليست مطلوبة على Hostinger.

### أوامر شائعة

```bash
# إحصاءات عبر API بعد تشغيل PHP
curl http://127.0.0.1:8765/api/stats

# قائمة / بحث / عرض عبر API
curl "http://127.0.0.1:8765/api/taxa?habit=شجرة&view=summary"
curl "http://127.0.0.1:8765/api/taxa?q=بلوط&view=summary"
curl "http://127.0.0.1:8765/api/taxa?family=Fagaceae&zone=MOUNTAIN_FOREST&view=summary"
curl "http://127.0.0.1:8765/api/taxa?category=trees&native=true&view=summary"
curl http://127.0.0.1:8765/api/taxa/FAG-QUE-AEG

# القيم المسموحة
curl http://127.0.0.1:8765/api/enums
```

### استخدام برمجي

استخدم REST API من أي تطبيق PHP/JS أو من الواجهة مباشرة. مثال PHP مختصر:

```php
$stats = json_decode(file_get_contents("http://127.0.0.1:8765/api/stats"), true);
$hits = json_decode(file_get_contents("http://127.0.0.1:8765/api/taxa?q=" . urlencode("بلوط")), true);
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
2. أضف/عدّل عبر الواجهة أو REST API في `api/index.php` (لا تحرّر الملفات المشتقة يدوياً).
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
- خطة الإطلاق / البيتا: [`plan.md`](plan.md)
- سجل العمليات الآلي: [`data/changelog.jsonl`](data/changelog.jsonl)
- المخطط: [`schema/`](schema/)
- واجهة REST: [`api/index.php`](api/index.php)
- الواجهة: [`file.bat`](file.bat) / [`router.php`](router.php) / [`frontend/`](frontend/)
