/**
 * API client for Iraqi Flora Encyclopedia local server.
 * Includes auth (Google session cookie) + flora CRUD + change requests.
 */
const API = (() => {
  const BASE = "";

  async function request(path, options = {}) {
    const opts = {
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(options.headers || {}) },
      ...options,
    };
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(`${BASE}${path}`, opts);
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`استجابة غير صالحة (${res.status})`);
    }
    if (!res.ok || data.ok === false) {
      const err = new Error(data.error || `خطأ HTTP ${res.status}`);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  function qs(params) {
    const sp = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      sp.set(k, String(v));
    });
    const s = sp.toString();
    return s ? `?${s}` : "";
  }

  return {
    // flora
    health: () => request("/api/health"),
    stats: () => request("/api/stats"),
    enums: () => request("/api/enums"),
    meta: () => request("/api/meta"),
    listTaxa: (params = {}) => request(`/api/taxa${qs(params)}`),
    getTaxon: (id) => request(`/api/taxa/${encodeURIComponent(id)}`),
    createTaxon: (body) => request("/api/taxa", { method: "POST", body }),
    updateTaxon: (id, body, replace = false) =>
      request(`/api/taxa/${encodeURIComponent(id)}`, {
        method: replace ? "PUT" : "PATCH",
        body: replace ? { ...body, _replace: true } : body,
      }),
    deleteTaxon: (id) =>
      request(`/api/taxa/${encodeURIComponent(id)}`, { method: "DELETE" }),
    suggestId: (family, genus, scientific_name) =>
      request("/api/suggest-id", {
        method: "POST",
        body: { family, genus, scientific_name },
      }),

    // auth
    authConfig: () => request("/api/auth/config"),
    me: () => request("/api/auth/me"),
    logout: () => request("/api/auth/logout", { method: "POST", body: {} }),
    googleStartUrl: () => "/api/auth/google/start",
    googleStartJson: () =>
      request("/api/auth/google/start?format=json", {
        headers: { Accept: "application/json" },
      }),
    devLogin: (email, name = "") =>
      request("/api/auth/dev-login", {
        method: "POST",
        body: { email, name },
      }),
    redeemCode: (code) =>
      request("/api/auth/redeem-code", { method: "POST", body: { code } }),

    // owner admin tools
    listUsers: () => request("/api/auth/admin/users"),
    listCodes: () => request("/api/auth/admin/codes"),
    generateCode: (note = "") =>
      request("/api/auth/admin/codes", { method: "POST", body: { note } }),
    revokeCode: (id) =>
      request(`/api/auth/admin/codes/${encodeURIComponent(id)}`, {
        method: "DELETE",
      }),
    demoteAdmin: (email) =>
      request(
        `/api/auth/admin/users/${encodeURIComponent(email)}/admin`,
        { method: "DELETE" }
      ),
    activity: (limit = 100) =>
      request(`/api/auth/activity${qs({ limit })}`),

    // change requests
    listRequests: (params = {}) => request(`/api/requests${qs(params)}`),
    getRequest: (id) => request(`/api/requests/${encodeURIComponent(id)}`),
    createRequest: (body) =>
      request("/api/requests", { method: "POST", body }),
    approveRequest: (id, note = "") =>
      request(`/api/requests/${encodeURIComponent(id)}/approve`, {
        method: "POST",
        body: { note },
      }),
    rejectRequest: (id, note = "") =>
      request(`/api/requests/${encodeURIComponent(id)}/reject`, {
        method: "POST",
        body: { note },
      }),
  };
})();
