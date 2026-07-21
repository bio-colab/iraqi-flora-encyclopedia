/**
 * API client for Iraqi Flora Encyclopedia local server.
 */
const API = (() => {
  const BASE = "";

  async function request(path, options = {}) {
    const opts = {
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
    health: () => request("/api/health"),
    stats: () => request("/api/stats"),
    enums: () => request("/api/enums"),
    meta: () => request("/api/meta"),
    listTaxa: (params = {}) => request(`/api/taxa${qs(params)}`),
    getTaxon: (id) => request(`/api/taxa/${encodeURIComponent(id)}`),
    createTaxon: (body) =>
      request("/api/taxa", { method: "POST", body }),
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
  };
})();
