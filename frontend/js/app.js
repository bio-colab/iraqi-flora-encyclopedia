/**
 * Iraqi Flora Encyclopedia — interactive frontend with Google auth + roles
 */
(function () {
  "use strict";

  const defaultPerms = () => ({
    can_view: true,
    can_request_changes: false,
    can_edit: false,
    can_manage_requests: false,
    can_view_activity: false,
    can_manage_admins: false,
    can_generate_codes: false,
    is_owner: false,
    is_admin: false,
    is_authenticated: false,
  });

  const state = {
    enums: null,
    meta: null,
    stats: null,
    results: [],
    total: 0,
    view: localStorage.getItem("flora_view") || "table",
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
    modal: null,
    user: null,
    permissions: defaultPerms(),
    authConfig: null,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // ---------- bootstrap ----------
  async function init() {
    bindChrome();
    setView(state.view, false);
    setLoading(true);
    try {
      await refreshAuth();
      handleAuthQueryParams();
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
      applyPermissionsUI();
      await loadResults();
    } catch (e) {
      toast(e.message || "فشل الاتصال بالخادم", "error");
      showEmpty("تعذّر تحميل البيانات. تأكد أن الخادم يعمل.");
    } finally {
      setLoading(false);
    }
  }

  function handleAuthQueryParams() {
    const sp = new URLSearchParams(location.search);
    if (sp.get("auth") === "ok") {
      toast("تم تسجيل الدخول بنجاح", "success");
      history.replaceState({}, "", location.pathname);
    }
    const err = sp.get("auth_error");
    if (err) {
      toast(err, "error");
      history.replaceState({}, "", location.pathname);
    }
  }

  async function refreshAuth() {
    try {
      const [cfg, me] = await Promise.all([API.authConfig(), API.me()]);
      state.authConfig = cfg.data;
      state.user = me.data.user || null;
      state.permissions = me.data.permissions || defaultPerms();
    } catch {
      state.user = null;
      state.permissions = defaultPerms();
    }
    renderAuthHeader();
    applyPermissionsUI();
  }

  function bindChrome() {
    $("#searchInput").addEventListener(
      "input",
      debounce(() => {
        state.filters.q = $("#searchInput").value.trim();
        loadResults();
      }, 280)
    );

    $("#searchInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        state.filters.q = $("#searchInput").value.trim();
        loadResults();
      }
    });

    $$(".view-toggle button").forEach((btn) => {
      btn.addEventListener("click", () => setView(btn.dataset.view));
    });

    $("#btnAdd").addEventListener("click", () => {
      if (state.permissions.can_edit) openForm("create");
      else if (state.permissions.can_request_changes) openForm("create", null, null, true);
      else toast("سجّل الدخول لطلب إضافة", "error");
    });

    $("#btnMyRequests")?.addEventListener("click", () => openRequestsPanel(true));
    $("#btnPanel")?.addEventListener("click", openAdminPanel);

    $("#btnResetFilters").addEventListener("click", resetFilters);
    $("#btnApplyFilters").addEventListener("click", () => {
      readFiltersFromSidebar();
      loadResults();
    });

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

    document.addEventListener("click", (e) => {
      const loginBtn = e.target.closest("#btnLogin");
      if (loginBtn) {
        e.preventDefault();
        startLogin();
      }
      const logoutBtn = e.target.closest("#btnLogout");
      if (logoutBtn) {
        e.preventDefault();
        doLogout();
      }
      const redeemBtn = e.target.closest("#btnRedeemOpen");
      if (redeemBtn) {
        e.preventDefault();
        openRedeemModal();
      }
    });
  }

  // ---------- auth UI ----------
  function renderAuthHeader() {
    const box = $("#headerAuth");
    if (!box) return;
    const u = state.user;
    if (!u) {
      box.innerHTML = `
        <button type="button" class="btn btn-primary btn-sm" id="btnLogin">
          دخول بحساب Google
        </button>`;
      return;
    }
    const roleLabel = roleLabelAr(u.role);
    box.innerHTML = `
      <div class="user-chip">
        ${u.picture ? `<img class="user-avatar" src="${esc(u.picture)}" alt="" referrerpolicy="no-referrer" />` : `<span class="user-avatar placeholder">👤</span>`}
        <div class="user-meta">
          <span class="user-name">${esc(u.name || u.email)}</span>
          <span class="user-role badge role-${esc(u.role)}">${esc(roleLabel)}</span>
        </div>
        <div class="user-actions">
          ${u.role === "user" ? `<button type="button" class="btn btn-sm" id="btnRedeemOpen">كود ترقية</button>` : ""}
          <button type="button" class="btn btn-sm" id="btnLogout">خروج</button>
        </div>
      </div>`;
  }

  function roleLabelAr(role) {
    return (
      {
        owner: "المالك",
        admin: "مدير",
        user: "مستخدم",
        guest: "ضيف",
      }[role] || role || "ضيف"
    );
  }

  function applyPermissionsUI() {
    const p = state.permissions;
    const btnAdd = $("#btnAdd");
    const btnReq = $("#btnMyRequests");
    const btnPanel = $("#btnPanel");

    if (p.can_edit) {
      btnAdd?.classList.remove("hidden");
      btnAdd.textContent = "＋ إضافة صنف";
    } else if (p.can_request_changes) {
      btnAdd?.classList.remove("hidden");
      btnAdd.textContent = "＋ طلب إضافة";
    } else {
      btnAdd?.classList.add("hidden");
    }

    if (p.is_authenticated && !p.can_edit) {
      btnReq?.classList.remove("hidden");
    } else if (p.can_manage_requests) {
      btnReq?.classList.remove("hidden");
      btnReq.textContent = "الطلبات";
    } else {
      btnReq?.classList.add("hidden");
    }

    if (p.can_view_activity || p.can_manage_admins || p.can_manage_requests) {
      btnPanel?.classList.remove("hidden");
    } else {
      btnPanel?.classList.add("hidden");
    }

    const banner = $("#roleBanner");
    if (!banner) return;
    if (!p.is_authenticated) {
      banner.innerHTML = `<div class="banner banner-info">أنت تتصفح كضيف — العرض فقط. سجّل الدخول لطلب إضافة أو تعديل.</div>`;
    } else if (p.is_owner) {
      banner.innerHTML = `<div class="banner banner-owner">حساب المالك — صلاحيات كاملة + إدارة المدراء وأكواد الترقية.</div>`;
    } else if (p.is_admin) {
      banner.innerHTML = `<div class="banner banner-admin">حساب مدير — يمكنك التعديل المباشر ومراجعة الطلبات وسجل النشاط.</div>`;
    } else {
      banner.innerHTML = `<div class="banner banner-user">حساب مستخدم — يمكنك إرسال طلبات إضافة / تعديل / حذف للمراجعة.</div>`;
    }
  }

  async function startLogin() {
    const cfg = state.authConfig;
    if (cfg?.oauth_configured) {
      location.href = API.googleStartUrl();
      return;
    }
    if (cfg?.allow_dev_login) {
      openDevLoginModal();
      return;
    }
    openModalShell();
    $("#modalShell").classList.add("modal-wide");
    $("#modalTitle").textContent = "إعداد تسجيل Google";
    $("#modalSub").textContent = "OAuth غير مُعدّ بعد";
    $("#modalBody").innerHTML = `
      <div class="detail-block">
        <p>لتفعيل الدخول بحساب Google:</p>
        <ol class="setup-steps">
          <li>أنشئ OAuth Client في Google Cloud Console (نوع Web).</li>
          <li>أضف Redirect URI:
            <code dir="ltr">http://127.0.0.1:8765/api/auth/google/callback</code>
          </li>
          <li>انسخ الملف <code>auth_config.example.json</code> إلى <code>auth_config.json</code>
            واملأ <code>google_client_id</code> و <code>google_client_secret</code>.</li>
          <li>أعد تشغيل الخادم.</li>
        </ol>
        <p class="text-muted">المالك الثابت: <strong dir="ltr">${esc(cfg?.owner_email || "aliasbio95@gmail.com")}</strong></p>
      </div>`;
    $("#modalFooter").innerHTML = `<button class="btn btn-ghost" id="mfClose">إغلاق</button>`;
    $("#mfClose").onclick = closeModal;
  }

  function openDevLoginModal() {
    openModalShell();
    $("#modalShell").classList.remove("modal-wide");
    $("#modalTitle").textContent = "دخول تجريبي (تطوير)";
    $("#modalSub").textContent = "allow_dev_login مفعّل — للاختبار المحلي فقط";
    $("#modalBody").innerHTML = `
      <form id="devLoginForm" class="form-grid" onsubmit="return false;">
        <div class="field full">
          <label for="devEmail">البريد</label>
          <input id="devEmail" type="email" dir="ltr" placeholder="you@example.com" required />
        </div>
        <div class="field full">
          <label for="devName">الاسم (اختياري)</label>
          <input id="devName" type="text" placeholder="الاسم الظاهر" />
        </div>
        <p class="text-muted full">للحصول على صلاحية المالك استخدم:
          <code dir="ltr">aliasbio95@gmail.com</code>
        </p>
      </form>`;
    $("#modalFooter").innerHTML = `
      <button class="btn btn-ghost" id="mfClose">إلغاء</button>
      <button class="btn btn-primary" id="mfDevLogin">دخول</button>`;
    $("#mfClose").onclick = closeModal;
    $("#mfDevLogin").onclick = async () => {
      const email = $("#devEmail").value.trim();
      const name = $("#devName").value.trim();
      if (!email) {
        toast("أدخل البريد", "error");
        return;
      }
      setLoading(true);
      try {
        await API.devLogin(email, name);
        toast("تم الدخول", "success");
        closeModal();
        await refreshAuth();
        await loadResults();
      } catch (e) {
        toast(e.message, "error");
      } finally {
        setLoading(false);
      }
    };
  }

  async function doLogout() {
    setLoading(true);
    try {
      await API.logout();
      toast("تم تسجيل الخروج", "success");
      await refreshAuth();
      await loadResults();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function openRedeemModal() {
    openModalShell();
    $("#modalShell").classList.remove("modal-wide");
    $("#modalTitle").textContent = "ترقية إلى مدير";
    $("#modalSub").textContent = "أدخل الكود الذي أرسله المالك (لمرة واحدة)";
    $("#modalBody").innerHTML = `
      <div class="field">
        <label for="redeemCode">كود الترقية</label>
        <input id="redeemCode" dir="ltr" placeholder="XXXX-XXXX-XX" autocomplete="off" />
      </div>`;
    $("#modalFooter").innerHTML = `
      <button class="btn btn-ghost" id="mfClose">إلغاء</button>
      <button class="btn btn-primary" id="mfRedeem">تفعيل</button>`;
    $("#mfClose").onclick = closeModal;
    $("#mfRedeem").onclick = async () => {
      const code = $("#redeemCode").value.trim();
      if (!code) {
        toast("أدخل الكود", "error");
        return;
      }
      setLoading(true);
      try {
        const res = await API.redeemCode(code);
        toast(res.message || "أصبحت مديراً", "success");
        closeModal();
        await refreshAuth();
        await loadResults();
      } catch (e) {
        toast(e.message, "error");
      } finally {
        setLoading(false);
      }
    };
  }

  // ---------- filters ----------
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

    const fams = (state.stats?.top_families || []).map((x) => x[0]);
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
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val ?? "—";
    };
    set("statTotal", s.total);
    set("statNative", s.native);
    set("statFamilies", s.families);
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

      if (state.results.length) {
        const fams = [
          ...new Set(state.results.map((r) => r.family).filter(Boolean)),
        ].sort();
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

  function actionButtons(t) {
    const p = state.permissions;
    let html = `<button class="btn btn-sm" data-act="view" data-id="${esc(t.id)}">عرض</button>`;
    if (p.can_edit) {
      html += `
        <button class="btn btn-sm" data-act="edit" data-id="${esc(t.id)}">تعديل</button>
        <button class="btn btn-sm btn-danger" data-act="del" data-id="${esc(t.id)}">حذف</button>`;
    } else if (p.can_request_changes) {
      html += `
        <button class="btn btn-sm" data-act="req-edit" data-id="${esc(t.id)}">طلب تعديل</button>
        <button class="btn btn-sm btn-danger" data-act="req-del" data-id="${esc(t.id)}">طلب حذف</button>`;
    }
    return html;
  }

  function renderTable(rows) {
    const body = rows
      .map(
        (t) => `
      <tr data-id="${esc(t.id)}">
        <td><span class="badge id-badge">${esc(t.id)}</span></td>
        <td class="sci">${esc(t.scientific_name || "")}</td>
        <td>${esc(t.arabic || "—")}</td>
        <td><span class="badge family-tag">${esc(t.family || "—")}</span></td>
        <td><span class="badge badge-habit">${esc(habitLabel(t.habit))}</span></td>
        <td>${nativeBadge(t.native_to_iraq)}</td>
        <td class="actions" onclick="event.stopPropagation()">
          ${actionButtons(t)}
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
        <div class="card-id"><span class="badge id-badge">${esc(t.id)}</span></div>
        <div class="card-sci">${esc(t.scientific_name || "")}</div>
        ${!compact ? `<div class="card-ar">${esc(t.arabic || "—")}</div>` : ""}
        <div class="card-meta">
          <span class="badge badge-habit">${esc(habitLabel(t.habit))}</span>
          ${t.family ? `<span class="badge family-tag">${esc(t.family)}</span>` : ""}
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
        else if (act === "req-edit") openForm("edit", id, null, true);
        else if (act === "req-del") confirmRequestDelete(id);
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
      $("#modalShell").classList.remove("modal-wide");
      $("#modalTitle").textContent =
        t.names?.arabic?.[0]?.name || t.scientific_name;
      $("#modalSub").textContent = t.scientific_name || "";
      $("#modalBody").innerHTML = renderDetail(t);
      const p = state.permissions;
      let footer = `<button class="btn btn-ghost" id="mfClose">إغلاق</button>`;
      if (p.can_edit) {
        footer += `
          <button class="btn" id="mfEdit">تعديل</button>
          <button class="btn btn-danger" id="mfDel">حذف</button>`;
      } else if (p.can_request_changes) {
        footer += `
          <button class="btn" id="mfReqEdit">طلب تعديل</button>
          <button class="btn btn-danger" id="mfReqDel">طلب حذف</button>`;
      }
      $("#modalFooter").innerHTML = footer;
      $("#mfClose").onclick = closeModal;
      if ($("#mfEdit")) $("#mfEdit").onclick = () => openForm("edit", t.id, t);
      if ($("#mfDel")) $("#mfDel").onclick = () => confirmDelete(t.id);
      if ($("#mfReqEdit"))
        $("#mfReqEdit").onclick = () => openForm("edit", t.id, t, true);
      if ($("#mfReqDel")) $("#mfReqDel").onclick = () => confirmRequestDelete(t.id);
      openModalShell();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function renderDetail(t) {
    const ar = (t.names?.arabic || [])
      .map(
        (n) =>
          `<li>${esc(n.name)} <span class="badge">${esc(n.confidence || "")}</span></li>`
      )
      .join("");
    const ku = (t.names?.kurdish || [])
      .map(
        (n) =>
          `<li>${esc(n.name)} <span class="badge">${esc(n.confidence || "")}</span></li>`
      )
      .join("");
    const en = (t.names?.english || []).map((n) => `<li>${esc(n)}</li>`).join("");
    const zones = (t.zones || [])
      .map((z) => `<span class="badge zone-pill">${esc(z)}</span>`)
      .join(" ");

    return `
      <div class="kv-grid">
        <div class="kv"><span class="k">المعرّف</span><div class="v"><span class="badge id-badge">${esc(t.id)}</span></div></div>
        <div class="kv"><span class="k">العائلة</span><div class="v"><span class="badge family-tag">${esc(t.classification?.family || "—")}</span></div></div>
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

  // ---------- form create/edit / request ----------
  async function openForm(mode, id, preloaded, asRequest = false) {
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
      const isRequest =
        asRequest ||
        (state.permissions.can_request_changes && !state.permissions.can_edit);
      state.modal = {
        mode,
        taxon,
        originalId: taxon.id,
        asRequest: isRequest,
      };
      $("#modalShell").classList.remove("modal-wide");
      const titleBase =
        mode === "create"
          ? isRequest
            ? "طلب إضافة صنف"
            : "إضافة صنف جديد"
          : isRequest
            ? `طلب تعديل: ${taxon.id}`
            : `تعديل: ${taxon.id}`;
      $("#modalTitle").textContent = titleBase;
      $("#modalSub").textContent = isRequest
        ? "سيُراجع الطلب من مدير قبل التطبيق"
        : mode === "create"
          ? "وفق مخطط plant_taxon"
          : taxon.scientific_name || "";
      $("#modalBody").innerHTML =
        renderForm(taxon, mode) +
        (isRequest
          ? `<div class="field full" style="margin-top:1rem">
              <label for="f_req_note">ملاحظة للمدير (اختياري)</label>
              <textarea id="f_req_note" rows="2" placeholder="سبب الطلب أو مصدر البيانات…"></textarea>
            </div>`
          : "");
      $("#modalFooter").innerHTML = `
        <button class="btn btn-ghost" id="mfClose">إلغاء</button>
        ${
          mode === "edit" && !isRequest && state.permissions.can_edit
            ? `<button class="btn btn-danger" id="mfDel">حذف</button>`
            : ""
        }
        <button class="btn" id="mfSuggest" type="button">اقتراح معرّف</button>
        <button class="btn btn-primary" id="mfSave">${isRequest ? "إرسال الطلب" : "حفظ"}</button>
      `;
      $("#mfClose").onclick = closeModal;
      $("#mfSave").onclick = () => saveForm();
      $("#mfSuggest").onclick = () => doSuggestId();
      if ($("#mfDel")) $("#mfDel").onclick = () => confirmDelete(taxon.id);
      $("#f_native")?.addEventListener("change", syncNativeFields);
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
    const habitOpts = (e.habit || [])
      .map(
        (h) =>
          `<option value="${esc(h)}" ${t.habit === h ? "selected" : ""}>${esc(habitLabel(h))} — ${esc(h)}</option>`
      )
      .join("");
    const presenceOpts = (e.presence_in_iraq || [])
      .map(
        (v) =>
          `<option value="${esc(v)}" ${t.presence_in_iraq === v ? "selected" : ""}>${esc(v)}</option>`
      )
      .join("");
    const statusOpts = (e.iraq_local_status || [])
      .map(
        (v) =>
          `<option value="${esc(v)}" ${t.iraq_local_status === v ? "selected" : ""}>${esc(v)}</option>`
      )
      .join("");
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
          <input id="f_id" value="${esc(t.id || "")}" placeholder="FAG-QUE-AEG" dir="ltr" />
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

    const asRequest = state.modal?.asRequest;
    const note = $("#f_req_note")?.value?.trim() || "";

    setLoading(true);
    try {
      if (asRequest) {
        if (state.modal.mode === "create") {
          if (!body.id) {
            const sug = await API.suggestId(
              body.classification.family,
              body.classification.genus,
              body.scientific_name
            );
            body.id = sug.data.id;
          }
          await API.createRequest({
            type: "add",
            payload: body,
            note,
          });
          toast("أُرسل طلب الإضافة للمراجعة", "success");
        } else {
          await API.createRequest({
            type: "update",
            taxon_id: state.modal.originalId,
            payload: body,
            note,
          });
          toast("أُرسل طلب التعديل للمراجعة", "success");
        }
        closeModal();
      } else {
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
          const res = await API.updateTaxon(id, body, true);
          toast(res.message || `عُدّل ${res.data.id}`, "success");
        }
        closeModal();
        const statsRes = await API.stats();
        state.stats = statsRes.data;
        updateHeaderStats();
        await loadResults();
      }
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  async function confirmDelete(id) {
    const ok = window.confirm(
      `هل تريد حذف الصنف ${id} نهائياً؟\nسيتم تحديث كل ملفات البيانات.`
    );
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

  async function confirmRequestDelete(id) {
    const note = window.prompt(`طلب حذف ${id}\nملاحظة للمدير (اختياري):`, "") ?? null;
    if (note === null) return;
    setLoading(true);
    try {
      await API.createRequest({
        type: "delete",
        taxon_id: id,
        note: note || "",
      });
      toast("أُرسل طلب الحذف للمراجعة", "success");
      closeModal();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  // ---------- admin / requests panel ----------
  async function openRequestsPanel(mineDefault) {
    setLoading(true);
    try {
      const isAdmin = state.permissions.can_manage_requests;
      const params = isAdmin && !mineDefault ? { status: "pending" } : { mine: "1" };
      if (isAdmin && mineDefault) params.mine = "1";
      const res = await API.listRequests(params);
      const rows = res.data || [];
      $("#modalShell").classList.add("modal-wide");
      $("#modalTitle").textContent = isAdmin ? "طلبات التعديل" : "طلباتي";
      $("#modalSub").textContent = isAdmin
        ? "موافقة المدير تطبّق التغيير فوراً"
        : "حالة الطلبات التي أرسلتها";
      $("#modalBody").innerHTML = renderRequestsTable(rows, isAdmin);
      $("#modalFooter").innerHTML = `
        <button class="btn btn-ghost" id="mfClose">إغلاق</button>
        ${
          isAdmin
            ? `<button class="btn" id="mfAllReq">كل الطلبات</button>
               <button class="btn" id="mfPendReq">المعلّقة فقط</button>`
            : ""
        }`;
      $("#mfClose").onclick = closeModal;
      if ($("#mfAllReq"))
        $("#mfAllReq").onclick = async () => {
          const r = await API.listRequests({});
          $("#modalBody").innerHTML = renderRequestsTable(r.data || [], true);
          bindRequestActions();
        };
      if ($("#mfPendReq"))
        $("#mfPendReq").onclick = async () => {
          const r = await API.listRequests({ status: "pending" });
          $("#modalBody").innerHTML = renderRequestsTable(r.data || [], true);
          bindRequestActions();
        };
      bindRequestActions();
      openModalShell();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function renderRequestsTable(rows, isAdmin) {
    if (!rows.length) {
      return `<div class="empty-state"><p>لا توجد طلبات.</p></div>`;
    }
    const body = rows
      .map((r) => {
        const actions =
          isAdmin && r.status === "pending"
            ? `<button class="btn btn-sm btn-primary" data-req="approve" data-id="${esc(r.id)}">موافقة</button>
               <button class="btn btn-sm btn-danger" data-req="reject" data-id="${esc(r.id)}">رفض</button>`
            : "";
        return `<tr>
          <td class="mono">${esc(r.id)}</td>
          <td>${esc(r.type)}</td>
          <td><span class="badge status-${esc(r.status)}">${esc(r.status)}</span></td>
          <td dir="ltr">${esc(r.requester_email || "")}</td>
          <td class="mono">${esc(r.taxon_id || "—")}</td>
          <td>${esc(r.note || "—")}</td>
          <td>${esc(r.created_at || "")}</td>
          <td class="actions">${actions}</td>
        </tr>`;
      })
      .join("");
    return `<div class="table-wrap"><table class="data-table">
      <thead><tr>
        <th>المعرّف</th><th>النوع</th><th>الحالة</th><th>مقدّم الطلب</th>
        <th>صنف</th><th>ملاحظة</th><th>التاريخ</th><th></th>
      </tr></thead>
      <tbody>${body}</tbody>
    </table></div>`;
  }

  function bindRequestActions() {
    $$("[data-req]").forEach((btn) => {
      btn.onclick = async () => {
        const id = btn.dataset.id;
        const act = btn.dataset.req;
        const note =
          window.prompt(act === "approve" ? "ملاحظة الموافقة (اختياري):" : "سبب الرفض (اختياري):", "") ??
          null;
        if (note === null) return;
        setLoading(true);
        try {
          if (act === "approve") {
            const res = await API.approveRequest(id, note);
            toast(res.message || "وُوفق وطُبّق", "success");
            const statsRes = await API.stats();
            state.stats = statsRes.data;
            updateHeaderStats();
            await loadResults();
          } else {
            const res = await API.rejectRequest(id, note);
            toast(res.message || "رُفض", "success");
          }
          const r = await API.listRequests({ status: "pending" });
          $("#modalBody").innerHTML = renderRequestsTable(r.data || [], true);
          bindRequestActions();
        } catch (e) {
          toast(e.message, "error");
        } finally {
          setLoading(false);
        }
      };
    });
  }

  async function openAdminPanel() {
    const p = state.permissions;
    if (!p.can_view_activity && !p.can_manage_admins) {
      toast("لوحة الإدارة للمديرين فقط", "error");
      return;
    }
    setLoading(true);
    try {
      const tabs = [];
      if (p.can_manage_requests) tabs.push(["requests", "الطلبات"]);
      if (p.can_view_activity) tabs.push(["activity", "سجل النشاط"]);
      if (p.can_manage_admins) {
        tabs.push(["codes", "أكواد الترقية"]);
        tabs.push(["users", "المستخدمون"]);
      }

      $("#modalShell").classList.add("modal-wide");
      $("#modalTitle").textContent = "لوحة الإدارة";
      $("#modalSub").textContent = p.is_owner
        ? "أدوات المالك والمدير"
        : "أدوات المدير";
      $("#modalBody").innerHTML = `
        <div class="admin-tabs" id="adminTabs">
          ${tabs
            .map(
              ([id, label], i) =>
                `<button type="button" class="btn btn-sm ${i === 0 ? "btn-primary" : ""}" data-tab="${id}">${label}</button>`
            )
            .join("")}
        </div>
        <div id="adminTabBody" class="admin-tab-body"></div>`;
      $("#modalFooter").innerHTML = `<button class="btn btn-ghost" id="mfClose">إغلاق</button>`;
      $("#mfClose").onclick = closeModal;

      const loadTab = async (tab) => {
        $$("#adminTabs [data-tab]").forEach((b) => {
          b.classList.toggle("btn-primary", b.dataset.tab === tab);
        });
        const body = $("#adminTabBody");
        body.innerHTML = `<p class="text-muted">جاري التحميل…</p>`;
        try {
          if (tab === "activity") {
            const res = await API.activity(150);
            body.innerHTML = renderActivity(res.data || []);
          } else if (tab === "requests") {
            const res = await API.listRequests({ status: "pending" });
            body.innerHTML = renderRequestsTable(res.data || [], true);
            bindRequestActions();
          } else if (tab === "codes") {
            await renderCodesPanel(body);
          } else if (tab === "users") {
            await renderUsersPanel(body);
          }
        } catch (e) {
          body.innerHTML = `<p class="toast error" style="position:static">${esc(e.message)}</p>`;
        }
      };

      $$("#adminTabs [data-tab]").forEach((b) => {
        b.onclick = () => loadTab(b.dataset.tab);
      });
      openModalShell();
      await loadTab(tabs[0][0]);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setLoading(false);
    }
  }

  function renderActivity(rows) {
    if (!rows.length) return `<div class="empty-state"><p>لا نشاط بعد.</p></div>`;
    const body = rows
      .map(
        (a) => `<tr>
        <td>${esc(a.ts || "")}</td>
        <td dir="ltr">${esc(a.actor_email || "—")}</td>
        <td><span class="badge role-${esc(a.actor_role || "")}">${esc(roleLabelAr(a.actor_role))}</span></td>
        <td class="mono">${esc(a.action || "")}</td>
        <td class="mono">${esc(a.target || "")}</td>
      </tr>`
      )
      .join("");
    return `<div class="table-wrap"><table class="data-table">
      <thead><tr><th>الوقت</th><th>الفاعل</th><th>الدور</th><th>الإجراء</th><th>الهدف</th></tr></thead>
      <tbody>${body}</tbody>
    </table></div>`;
  }

  async function renderCodesPanel(body) {
    const res = await API.listCodes();
    const codes = res.data || [];
    body.innerHTML = `
      <div class="admin-toolbar">
        <div class="field" style="flex:1;margin:0">
          <label for="codeNote">ملاحظة للكود (اختياري)</label>
          <input id="codeNote" placeholder="مثلاً: لفلان" />
        </div>
        <button type="button" class="btn btn-primary" id="btnGenCode">توليد كود ترقية</button>
      </div>
      <div id="freshCodeBox" class="fresh-code hidden"></div>
      <div class="table-wrap" style="margin-top:1rem">
        <table class="data-table">
          <thead><tr>
            <th>الحالة</th><th>تلميح</th><th>أُنشئ</th><th>مستخدم بواسطة</th><th>ملاحظة</th><th></th>
          </tr></thead>
          <tbody>
            ${
              codes
                .map(
                  (c) => `<tr>
              <td><span class="badge status-${esc(c.status)}">${esc(c.status)}</span></td>
              <td class="mono" dir="ltr">${esc(c.hint || "")}</td>
              <td>${esc(c.created_at || "")}</td>
              <td dir="ltr">${esc(c.used_by || "—")}</td>
              <td>${esc(c.note || "—")}</td>
              <td>${
                c.status === "active"
                  ? `<button class="btn btn-sm btn-danger" data-revoke="${esc(c.id)}">إلغاء</button>`
                  : ""
              }</td>
            </tr>`
                )
                .join("") ||
              `<tr><td colspan="6">لا أكواد بعد</td></tr>`
            }
          </tbody>
        </table>
      </div>`;

    $("#btnGenCode").onclick = async () => {
      setLoading(true);
      try {
        const note = $("#codeNote").value.trim();
        const r = await API.generateCode(note);
        const box = $("#freshCodeBox");
        box.classList.remove("hidden");
        box.innerHTML = `
          <strong>الكود (يُعرض مرة واحدة فقط):</strong>
          <code class="big-code" dir="ltr">${esc(r.data.code)}</code>
          <p class="text-muted">صالح ${esc(String(r.data.expires_in_hours))} ساعة — انسخه وأرسله للمرشّح بأمان.</p>
          <button type="button" class="btn btn-sm" id="btnCopyCode">نسخ</button>`;
        $("#btnCopyCode").onclick = async () => {
          try {
            await navigator.clipboard.writeText(r.data.code);
            toast("نُسخ الكود", "success");
          } catch {
            toast("انسخ الكود يدوياً", "error");
          }
        };
        toast("تم توليد الكود", "success");
        await renderCodesPanel(body);
        // restore fresh box after re-render
        const box2 = $("#freshCodeBox");
        if (box2) {
          box2.classList.remove("hidden");
          box2.innerHTML = box.innerHTML;
          $("#btnCopyCode")?.addEventListener("click", async () => {
            try {
              await navigator.clipboard.writeText(r.data.code);
              toast("نُسخ الكود", "success");
            } catch {
              toast("انسخ الكود يدوياً", "error");
            }
          });
        }
      } catch (e) {
        toast(e.message, "error");
      } finally {
        setLoading(false);
      }
    };

    $$("[data-revoke]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("إلغاء هذا الكود؟")) return;
        try {
          await API.revokeCode(btn.dataset.revoke);
          toast("أُلغي الكود", "success");
          await renderCodesPanel(body);
        } catch (e) {
          toast(e.message, "error");
        }
      };
    });
  }

  async function renderUsersPanel(body) {
    const res = await API.listUsers();
    const users = res.data || [];
    body.innerHTML = `
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>البريد</th><th>الاسم</th><th>الدور</th><th>آخر دخول</th><th></th>
          </tr></thead>
          <tbody>
            ${users
              .map((u) => {
                const canDemote = u.role === "admin";
                return `<tr>
                <td dir="ltr">${esc(u.email)}</td>
                <td>${esc(u.name || "—")}</td>
                <td><span class="badge role-${esc(u.role)}">${esc(roleLabelAr(u.role))}</span></td>
                <td>${esc(u.last_login_at || "—")}</td>
                <td>${
                  canDemote
                    ? `<button class="btn btn-sm btn-danger" data-demote="${esc(u.email)}">إزالة المدير</button>`
                    : ""
                }</td>
              </tr>`;
              })
              .join("")}
          </tbody>
        </table>
      </div>`;

    $$("[data-demote]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm(`إزالة صلاحية المدير عن ${btn.dataset.demote}؟`)) return;
        try {
          await API.demoteAdmin(btn.dataset.demote);
          toast("أُزيلت صلاحية المدير", "success");
          await renderUsersPanel(body);
        } catch (e) {
          toast(e.message, "error");
        }
      };
    });
  }

  // ---------- modal shell / utils ----------
  function openModalShell() {
    $("#modalBackdrop").classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    $("#modalBackdrop").classList.remove("open");
    $("#modalShell")?.classList.remove("modal-wide");
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
