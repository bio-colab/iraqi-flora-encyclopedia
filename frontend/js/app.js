/**
 * Iraqi Flora Encyclopedia — interactive CRUD frontend
 */
(function () {
  "use strict";

  const state = {
    enums: null,
    meta: null,
    stats: null,
    results: [],
    total: 0,
    view: localStorage.getItem("flora_view") || "table", // table | grid | cards
    loading: false,
    filters: {
      q: "",
      habit: "",
      family: "",
      genus: "",
      zone: "",
      native: "",
      presence: "",
      local_status: "",
      category: "",
      iucn: "",
    },
    modal: null, // { mode: 'view'|'edit'|'create', taxon }
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // ---------- bootstrap ----------
  async function init() {
    bindChrome();
    setView(state.view, false);
    setLoading(true);
    try {
      const [enumsRes, metaRes, statsRes] = await Promise.all([
        API.enums(),
        API.meta(),
        API.stats(),
      ]);
      state.enums = enumsRes.data;
      state.meta = metaRes.data;
      state.stats = statsRes.data;
      fillFilterOptions();
      updateHeaderStats();
      await loadResults();
    } catch (e) {
      toast(e.message || "فشل الاتصال بالخادم", "error");
      showEmpty("تعذّر تحميل البيانات. تأكد أن الخادم يعمل.");
    } finally {
      setLoading(false);
    }
  }

  function bindChrome() {
    $("#searchInput").addEventListener("input", debounce(() => {
      state.filters.q = $("#searchInput").value.trim();
      loadResults();
    }, 280));

    $("#searchInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        state.filters.q = $("#searchInput").value.trim();
        loadResults();
      }
    });

    $$(".view-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.dataset.view));
    });

    $("#btnAdd").addEventListener("click", () => openForm("create"));
    $("#btnResetFilters").addEventListener("click", resetFilters);
    $("#btnApplyFilters").addEventListener("click", () => {
      readFiltersFromSidebar();
      loadResults();
    });

    // sidebar live apply on change
    $$("#filterForm select, #filterForm input").forEach((el) => {
      el.addEventListener("change", () => {
        readFiltersFromSidebar();
        loadResults();
      });
    });

    $("#modalBackdrop").addEventListener("click", (e) => {
      if (e.target === $("#modalBackdrop")) closeModal();
    });
    $("#modalClose").addEventListener("click", closeModal);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  }

  function fillFilterOptions() {
    const e = state.enums;
    if (!e) return;

    fillSelect($("#filterHabit"), e.habit, (h) => {
      const m = e.habit_meta?.[h];
      return m ? `${m.label_ar} (${h})` : h;
    });
    fillSelect($("#filterZone"), e.zones);
    fillSelect($("#filterPresence"), e.presence_in_iraq);
    fillSelect($("#filterLocalStatus"), e.iraq_local_status);
    fillSelect($("#filterIucn"), e.iucn);
    fillSelect(
      $("#filterCategory"),
      Object.keys(e.category_groups || {}),
      (k) => e.category_groups[k]?.label_ar || k
    );

    // families from stats
    const fams = (state.stats?.top_families || []).map((x) => x[0]);
    // also pull unique from a full list request later; top is fine for filter seed
    fillSelect($("#filterFamily"), fams);
  }

  function fillSelect(select, values, labelFn) {
    if (!select) return;
    const first = select.querySelector("option");
    select.innerHTML = "";
    if (first) select.appendChild(first);
    else {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = "— الكل —";
      select.appendChild(o);
    }
    (values || []).forEach((v) => {
      const o = document.createElement("option");
      o.value = v;
      o.textContent = labelFn ? labelFn(v) : v;
      select.appendChild(o);
    });
  }

  function readFiltersFromSidebar() {
    state.filters.habit = $("#filterHabit").value;
    state.filters.family = $("#filterFamily").value;
    state.filters.genus = $("#filterGenus").value.trim();
    state.filters.zone = $("#filterZone").value;
    state.filters.native = $("#filterNative").value;
    state.filters.presence = $("#filterPresence").value;
    state.filters.local_status = $("#filterLocalStatus").value;
    state.filters.category = $("#filterCategory").value;
    state.filters.iucn = $("#filterIucn").value;
  }

  function resetFilters() {
    state.filters = {
      q: state.filters.q,
      habit: "",
      family: "",
      genus: "",
      zone: "",
      native: "",
      presence: "",
      local_status: "",
      category: "",
      iucn: "",
    };
    $("#filterForm").reset();
    loadResults();
  }

  function updateHeaderStats() {
    const s = state.stats;
    if (!s) return;
    $("#statTotal").textContent = s.total ?? "—";
    $("#statNative").textContent = s.native ?? "—";
    $("#statFamilies").textContent = s.families ?? "—";
  }

  // ---------- data ----------
  async function loadResults() {
    setLoading(true);
    try {
      const params = {
        q: state.filters.q,
        habit: state.filters.habit,
        family: state.filters.family,
        genus: state.filters.genus,
        zone: state.filters.zone,
        native: state.filters.native,
        presence: state.filters.presence,
        local_status: state.filters.local_status,
        category: state.filters.category,
        iucn: state.filters.iucn,
        limit: 500,
        view: "summary",
      };
      const res = await API.listTaxa(params);
      const data = res.data;
      state.results = data.results || [];
      state.total = data.total || 0;
      $("#resultCount").textContent = `${state.total} نتيجة`;

      // enrich family filter from current page if empty-ish
      if (state.results.length) {
        const fams = [...new Set(state.results.map((r) => r.family).filter(Boolean))].sort();
        const cur = $("#filterFamily").value;
        if ($("#filterFamily").options.length < 5) {
          fillSelect($("#filterFamily"), fams);
          $("#filterFamily").value = cur;
        }
      }

      renderResults();
    } catch (e) {
      toast(e.message, "error");
      showEmpty("خطأ أثناء البحث.");
    } finally {
      setLoading(false);
    }
  }

  // ---------- views ----------
  function setView(view, persist = true) {
    state.view = view;
    if (persist) localStorage.setItem("flora_view", view);
    $$(".view-toggle button").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    renderResults();
  }

  function renderResults() {
    const area = $("#resultsArea");
    if (!state.results.length) {
      showEmpty("لا توجد أصناف مطابقة. جرّب تعديل البحث أو المرشحات.");
      return;
    }
    if (state.view === "table") {
      area.innerHTML = renderTable(state.results);
    } else if (state.view === "grid") {
      area.innerHTML = `<div class="cards-grid grid-dense">${state.results
        .map((t) => renderCard(t, true))
        .join("")}</div>`;
    } else {
      area.innerHTML = `<div class="cards-grid">${state.results
        .map((t) => renderCard(t, false))
        .join("")}</div>`;
    }
    bindResultActions(area);
  }

  function showEmpty(msg) {
    $("#resultsArea").innerHTML = `
      <div class="empty-state">
        <span class="emoji">🌿</span>
        <p>${esc(msg)}</p>
      </div>`;
  }

  function renderTable(rows) {
    const body = rows
      .map(
        (t) => `
      <tr data-id="${esc(t.id)}">
        <td class="mono">${esc(t.id)}</td>
        <td class="sci">${esc(t.scientific_name || "")}</td>
        <td>${esc(t.arabic || "—")}</td>
        <td>${esc(t.family || "—")}</td>
        <td><span class="badge badge-habit">${esc(habitLabel(t.habit))}</span></td>
        <td>${nativeBadge(t.native_to_iraq)}</td>
        <td class="actions" onclick="event.stopPropagation()">
          <button class="btn btn-sm" data-act="view" data-id="${esc(t.id)}">عرض</button>
          <button class="btn btn-sm" data-act="edit" data-id="${esc(t.id)}">تعديل</button>
          <button class="btn btn-sm btn-danger" data-act="del" data-id="${esc(t.id)}">حذف</button>
        </td>
      </tr>`
      )
      .join("");

    return `
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>المعرّف</th>
              <th>الاسم العلمي</th>
              <th>العربي</th>
              <th>العائلة</th>
              <th>شكل النمو</th>
              <th>الأصالة</th>
              <th>إجراءات</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  function renderCard(t, compact) {
    return `
      <article class="taxon-card" data-id="${esc(t.id)}">
        <div class="card-id">${esc(t.id)}</div>
        <div class="card-sci">${esc(t.scientific_name || "")}</div>
        ${!compact ? `<div class="card-ar">${esc(t.arabic || "—")}</div>` : ""}
        <div class="card-meta">
          <span class="badge badge-habit">${esc(habitLabel(t.habit))}</span>
          ${t.family ? `<span class="badge">${esc(t.family)}</span>` : ""}
          ${nativeBadge(t.native_to_iraq)}
          ${t.iraq_local_status ? `<span class="badge badge-status">${esc(t.iraq_local_status)}</span>` : ""}
        </div>
      </article>`;
  }

  function bindResultActions(root) {
    $$("[data-id]", root).forEach((el) => {
      if (el.tagName === "TR" || el.classList.contains("taxon-card")) {
        el.addEventListener("click", () => openView(el.dataset.id));
      }
    });
    $$("[data-act]", root).forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const act = btn.dataset.act;
        if (act === "view") openView(id);
        else if (act === "edit") openForm("edit", id);
        else if (act === "del") confirmDelete(id);
      });
    });
  }

  function habitLabel(h) {
    const m = state.enums?.habit_meta?.[h];
    return m ? m.label_ar : h || "—";
  }

  function nativeBadge(n) {
    if (n === true) return `<span class="badge badge-native">أصيل</span>`;
    if (n === false) return `<span class="badge badge-alien">غير أصيل</span>`;
    return `<span class="badge">—</span>`;
  }

  // ---------- modal view ----------
  async function openView(id) {
    setLoading(true);
    try {
      const res = await API.getTaxon(id);
      const t = res.data;
      state.modal = { mode: "view", taxon: t };
      $("#modalTitle").textContent = t.names?.arabic?.[0]?.name || t.scientific_name;
      $("#modalSub").textContent = t.scientific_name || "";
      $("#modalBody").innerHTML = renderDetail(t);
      $("#modalFooter").innerHTML = `
        <button class="btn btn-ghost" id="mfClose">إغلاق</button>
        <button class="btn" id="mfEdit">تعديل</button>
        <button class="btn btn-danger" id="mfDel">حذف</button>
      `;
      $("#mfClose").onclick = closeModal;
      $("#mfEdit").onclick = () => openForm("edit", t.id, t);
      $("#mfDel").onclick = () => confirmDelete(t.id);
      openModalShell();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function renderDetail(t) {
    const ar = (t.names?.arabic || [])
      .map((n) => `<li>${esc(n.name)} <span class="badge">${esc(n.confidence || "")}</span></li>`)
      .join("");
    const ku = (t.names?.kurdish || [])
      .map((n) => `<li>${esc(n.name)} <span class="badge">${esc(n.confidence || "")}</span></li>`)
      .join("");
    const en = (t.names?.english || []).map((n) => `<li>${esc(n)}</li>`).join("");
    const zones = (t.zones || []).map((z) => `<span class="badge">${esc(z)}</span>`).join(" ");

    return `
      <div class="kv-grid">
        <div class="kv"><span class="k">المعرّف</span><div class="v mono">${esc(t.id)}</div></div>
        <div class="kv"><span class="k">العائلة</span><div class="v">${esc(t.classification?.family || "—")}</div></div>
        <div class="kv"><span class="k">الجنس</span><div class="v">${esc(t.classification?.genus || "—")}</div></div>
        <div class="kv"><span class="k">الرتبة</span><div class="v">${esc(t.classification?.order || "—")}</div></div>
        <div class="kv"><span class="k">شكل النمو</span><div class="v">${esc(habitLabel(t.habit))}</div></div>
        <div class="kv"><span class="k">الأصالة</span><div class="v">${t.native_to_iraq ? "أصيل في العراق" : "غير أصيل"}</div></div>
        <div class="kv"><span class="k">الحضور</span><div class="v">${esc(t.presence_in_iraq || "—")}</div></div>
        <div class="kv"><span class="k">الحالة المحلية</span><div class="v">${esc(t.iraq_local_status || "—")}</div></div>
        <div class="kv"><span class="k">IUCN</span><div class="v">${esc(t.iucn?.category ?? "غير مُسجَّل")}</div></div>
        <div class="kv"><span class="k">مستوطن</span><div class="v">${t.endemic_to_iraq ? "نعم" : "لا"}</div></div>
      </div>

      <div class="detail-block" style="margin-top:1rem">
        <h3>المناطق النباتية</h3>
        <p>${zones || "—"}</p>
      </div>

      ${t.flag ? `<div class="detail-block"><h3>تنبيه</h3><p>${esc(t.flag)}</p></div>` : ""}
      ${t.introduction_status ? `<div class="detail-block"><h3>حالة الإدخال</h3><p>${esc(t.introduction_status)}</p></div>` : ""}
      ${t.taxonomic_note ? `<div class="detail-block"><h3>ملاحظة تصنيفية</h3><p>${esc(t.taxonomic_note)}</p></div>` : ""}

      <div class="detail-block">
        <h3>الأسماء العربية</h3>
        <ul>${ar || "<li>—</li>"}</ul>
      </div>
      ${ku ? `<div class="detail-block"><h3>الأسماء الكردية</h3><ul>${ku}</ul></div>` : ""}
      <div class="detail-block">
        <h3>الأسماء الإنجليزية</h3>
        <ul>${en || "<li>—</li>"}</ul>
      </div>

      <div class="detail-block">
        <h3>ملاحظات</h3>
        <div class="notes-box">${esc(t.notes || "—")}</div>
      </div>
    `;
  }

  // ---------- form create/edit ----------
  async function openForm(mode, id, preloaded) {
    setLoading(true);
    try {
      let taxon = preloaded;
      if (mode === "edit" && !taxon) {
        const res = await API.getTaxon(id);
        taxon = res.data;
      }
      if (mode === "create") {
        taxon = blankTaxon();
      }
      state.modal = { mode, taxon, originalId: taxon.id };
      $("#modalTitle").textContent = mode === "create" ? "إضافة صنف جديد" : `تعديل: ${taxon.id}`;
      $("#modalSub").textContent = mode === "create" ? "وفق مخطط plant_taxon" : taxon.scientific_name || "";
      $("#modalBody").innerHTML = renderForm(taxon, mode);
      $("#modalFooter").innerHTML = `
        <button class="btn btn-ghost" id="mfClose">إلغاء</button>
        ${mode === "edit" ? `<button class="btn btn-danger" id="mfDel">حذف</button>` : ""}
        <button class="btn" id="mfSuggest" type="button">اقتراح معرّف</button>
        <button class="btn btn-primary" id="mfSave">حفظ</button>
      `;
      $("#mfClose").onclick = closeModal;
      $("#mfSave").onclick = () => saveForm();
      $("#mfSuggest").onclick = () => doSuggestId();
      if ($("#mfDel")) $("#mfDel").onclick = () => confirmDelete(taxon.id);
      $("#f_native").addEventListener("change", syncNativeFields);
      syncNativeFields();
      openModalShell();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function blankTaxon() {
    return {
      id: "",
      scientific_name: "",
      taxonomic_note: "",
      classification: { order: "", family: "", genus: "" },
      names: {
        arabic: [{ name: "", confidence: "عالية" }],
        kurdish: [],
        english: [""],
      },
      habit: "شجرة",
      zones: [],
      native_to_iraq: true,
      endemic_to_iraq: false,
      presence_in_iraq: "موجود",
      introduction_status: "",
      iucn: { category: null, verified_in_session: false },
      iraq_local_status: "غير_معروف",
      flag: "",
      flagship_case: false,
      notes: "",
    };
  }

  function renderForm(t, mode) {
    const e = state.enums || {};
    const habitOpts = (e.habit || []).map(
      (h) => `<option value="${esc(h)}" ${t.habit === h ? "selected" : ""}>${esc(habitLabel(h))} — ${esc(h)}</option>`
    ).join("");
    const presenceOpts = (e.presence_in_iraq || []).map(
      (v) => `<option value="${esc(v)}" ${t.presence_in_iraq === v ? "selected" : ""}>${esc(v)}</option>`
    ).join("");
    const statusOpts = (e.iraq_local_status || []).map(
      (v) => `<option value="${esc(v)}" ${t.iraq_local_status === v ? "selected" : ""}>${esc(v)}</option>`
    ).join("");
    const iucnOpts = [`<option value="">— null —</option>`]
      .concat(
        (e.iucn || []).map(
          (v) =>
            `<option value="${esc(v)}" ${t.iucn?.category === v ? "selected" : ""}>${esc(v)}</option>`
        )
      )
      .join("");
    const confOpts = (e.confidence || ["عالية", "متوسطة", "منخفضة"])
      .map(
        (c) =>
          `<option value="${esc(c)}" ${t.names?.arabic?.[0]?.confidence === c ? "selected" : ""}>${esc(c)}</option>`
      )
      .join("");
    const zones = e.zones || [];
    const selectedZones = new Set(t.zones || []);
    const zoneChecks = zones
      .map(
        (z) => `
        <label>
          <input type="checkbox" name="zone" value="${esc(z)}" ${selectedZones.has(z) ? "checked" : ""} />
          ${esc(z)}
        </label>`
      )
      .join("");

    const ar0 = t.names?.arabic?.[0]?.name || "";
    const en0 = (t.names?.english || [])[0] || "";
    const ku0 = t.names?.kurdish?.[0]?.name || "";

    return `
      <form id="taxonForm" class="form-grid" onsubmit="return false;">
        <div class="form-section">الهوية والتصنيف</div>
        <div class="field">
          <label for="f_id">المعرّف (FAM-GEN-SPP)</label>
          <input id="f_id" ${mode === "edit" ? "" : ""} value="${esc(t.id || "")}" placeholder="FAG-QUE-AEG" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_sci">الاسم العلمي *</label>
          <input id="f_sci" required value="${esc(t.scientific_name || "")}" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_family">العائلة *</label>
          <input id="f_family" required value="${esc(t.classification?.family || "")}" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_genus">الجنس *</label>
          <input id="f_genus" required value="${esc(t.classification?.genus || "")}" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_order">الرتبة</label>
          <input id="f_order" value="${esc(t.classification?.order || "")}" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_habit">شكل النمو *</label>
          <select id="f_habit">${habitOpts}</select>
        </div>
        <div class="field full">
          <label for="f_taxnote">ملاحظة تصنيفية</label>
          <input id="f_taxnote" value="${esc(t.taxonomic_note || "")}" />
        </div>

        <div class="form-section">الأسماء</div>
        <div class="field">
          <label for="f_ar">الاسم العربي *</label>
          <input id="f_ar" required value="${esc(ar0)}" />
        </div>
        <div class="field">
          <label for="f_ar_conf">ثقة الاسم العربي</label>
          <select id="f_ar_conf">${confOpts}</select>
        </div>
        <div class="field">
          <label for="f_en">الاسم الإنجليزي</label>
          <input id="f_en" value="${esc(en0)}" dir="ltr" />
        </div>
        <div class="field">
          <label for="f_ku">الاسم الكردي</label>
          <input id="f_ku" value="${esc(ku0)}" />
        </div>

        <div class="form-section">التوزيع والحالة</div>
        <div class="field full">
          <label>المناطق النباتية</label>
          <div class="zone-checks">${zoneChecks}</div>
        </div>
        <div class="field">
          <label class="checkbox-row" style="margin-top:0">
            <input type="checkbox" id="f_native" ${t.native_to_iraq !== false ? "checked" : ""} />
            أصيل في العراق
          </label>
        </div>
        <div class="field">
          <label class="checkbox-row" style="margin-top:0">
            <input type="checkbox" id="f_endemic" ${t.endemic_to_iraq ? "checked" : ""} />
            مستوطن في العراق
          </label>
        </div>
        <div class="field" id="introField">
          <label for="f_intro">حالة الإدخال (لغير الأصيل) *</label>
          <input id="f_intro" value="${esc(t.introduction_status || "")}" />
        </div>
        <div class="field">
          <label for="f_presence">الحضور في العراق</label>
          <select id="f_presence">${presenceOpts}</select>
        </div>
        <div class="field">
          <label for="f_status">الحالة المحلية</label>
          <select id="f_status">${statusOpts}</select>
        </div>
        <div class="field">
          <label for="f_iucn">رتبة IUCN</label>
          <select id="f_iucn">${iucnOpts}</select>
        </div>
        <div class="field">
          <label class="checkbox-row" style="margin-top:0">
            <input type="checkbox" id="f_iucn_ver" ${t.iucn?.verified_in_session ? "checked" : ""} />
            IUCN مُتحقق في الجلسة
          </label>
        </div>
        <div class="field">
          <label class="checkbox-row" style="margin-top:0">
            <input type="checkbox" id="f_flagship" ${t.flagship_case ? "checked" : ""} />
            حالة نموذجية (flagship)
          </label>
        </div>
        <div class="field full">
          <label for="f_flag">تنبيه / علم تحريري</label>
          <input id="f_flag" value="${esc(t.flag || "")}" />
        </div>
        <div class="field full">
          <label for="f_notes">ملاحظات *</label>
          <textarea id="f_notes" required>${esc(t.notes || "")}</textarea>
        </div>
      </form>
    `;
  }

  function syncNativeFields() {
    const native = $("#f_native")?.checked;
    const intro = $("#introField");
    if (intro) intro.style.opacity = native ? "0.45" : "1";
  }

  function collectForm() {
    const zones = $$('input[name="zone"]:checked').map((el) => el.value);
    const native = $("#f_native").checked;
    const arName = $("#f_ar").value.trim();
    const kuName = $("#f_ku").value.trim();
    const enName = $("#f_en").value.trim();
    const iucnCat = $("#f_iucn").value || null;

    const body = {
      id: $("#f_id").value.trim().toUpperCase(),
      scientific_name: $("#f_sci").value.trim(),
      taxonomic_note: $("#f_taxnote").value.trim() || undefined,
      classification: {
        order: $("#f_order").value.trim() || "Unknown",
        family: $("#f_family").value.trim(),
        genus: $("#f_genus").value.trim(),
      },
      names: {
        arabic: arName
          ? [{ name: arName, confidence: $("#f_ar_conf").value || "عالية" }]
          : [],
        english: enName ? [enName] : [],
      },
      habit: $("#f_habit").value,
      zones,
      native_to_iraq: native,
      endemic_to_iraq: $("#f_endemic").checked,
      presence_in_iraq: $("#f_presence").value,
      iucn: {
        category: iucnCat,
        verified_in_session: $("#f_iucn_ver").checked && !!iucnCat,
      },
      iraq_local_status: $("#f_status").value,
      flagship_case: $("#f_flagship").checked,
      notes: $("#f_notes").value.trim(),
    };

    if (kuName) {
      body.names.kurdish = [{ name: kuName, confidence: "متوسطة" }];
    }
    if (!native) {
      body.introduction_status = $("#f_intro").value.trim() || "غير أصيل";
    }
    const flag = $("#f_flag").value.trim();
    if (flag) body.flag = flag;
    else body.flag = null;

    // strip empty taxonomic_note
    if (!body.taxonomic_note) delete body.taxonomic_note;

    return body;
  }

  async function doSuggestId() {
    try {
      const family = $("#f_family").value.trim();
      const genus = $("#f_genus").value.trim();
      const sci = $("#f_sci").value.trim();
      if (!family || !genus || !sci) {
        toast("أدخل العائلة والجنس والاسم العلمي أولاً", "error");
        return;
      }
      const res = await API.suggestId(family, genus, sci);
      $("#f_id").value = res.data.id;
      toast(`معرّف مقترح: ${res.data.id}`, "success");
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function saveForm() {
    let body;
    try {
      body = collectForm();
    } catch (e) {
      toast(e.message, "error");
      return;
    }
    if (!body.scientific_name || !body.classification.family || !body.classification.genus) {
      toast("الحقول الإلزامية ناقصة", "error");
      return;
    }
    if (!body.names.arabic.length) {
      toast("يلزم اسم عربي واحد على الأقل", "error");
      return;
    }
    if (!body.notes) {
      toast("حقل الملاحظات مطلوب", "error");
      return;
    }

    setLoading(true);
    try {
      if (state.modal.mode === "create") {
        if (!body.id) {
          const sug = await API.suggestId(
            body.classification.family,
            body.classification.genus,
            body.scientific_name
          );
          body.id = sug.data.id;
        }
        const res = await API.createTaxon({ ...body, _suggest_id: false });
        toast(res.message || `أُضيف ${res.data.id}`, "success");
      } else {
        const id = state.modal.originalId;
        // full replace body to keep schema integrity
        const res = await API.updateTaxon(id, body, true);
        toast(res.message || `عُدّل ${res.data.id}`, "success");
      }
      closeModal();
      // refresh stats + list
      const statsRes = await API.stats();
      state.stats = statsRes.data;
      updateHeaderStats();
      await loadResults();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function confirmDelete(id) {
    const ok = window.confirm(`هل تريد حذف الصنف ${id} نهائياً؟\nسيتم تحديث كل ملفات البيانات.`);
    if (!ok) return;
    setLoading(true);
    try {
      const res = await API.deleteTaxon(id);
      toast(res.message || `حُذف ${id}`, "success");
      closeModal();
      const statsRes = await API.stats();
      state.stats = statsRes.data;
      updateHeaderStats();
      await loadResults();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  // ---------- modal shell / utils ----------
  function openModalShell() {
    $("#modalBackdrop").classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    $("#modalBackdrop").classList.remove("open");
    document.body.style.overflow = "";
    state.modal = null;
  }

  function setLoading(on) {
    state.loading = on;
    $("#loadingBar").classList.toggle("active", on);
  }

  function toast(msg, type = "success") {
    const box = $("#toasts");
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => {
      el.remove();
    }, 4200);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  document.addEventListener("DOMContentLoaded", init);
})();
