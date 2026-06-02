Object.assign(API, {
  getReports(status = "open") {
    return this.request(`/api/reports?status=${encodeURIComponent(status)}`);
  },

  submitReport(payload) {
    return this.request("/api/reports", { method: "POST", body: payload });
  },

  updateReport(reportId, payload) {
    return this.request(`/api/reports/${encodeURIComponent(reportId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  bulkUpdateReports(payload) {
    return this.request("/api/reports/bulk", {
      method: "POST",
      body: payload,
    });
  },

  addReportNote(reportId, payload) {
    return this.request(`/api/reports/${encodeURIComponent(reportId)}/notes`, {
      method: "POST",
      body: payload,
    });
  },

  getReportMacros() {
    return this.request("/api/reports/macros");
  },

  createReportMacro(payload) {
    return this.request("/api/reports/macros", {
      method: "POST",
      body: payload,
    });
  },

  updateReportMacro(macroId, payload) {
    return this.request(`/api/reports/macros/${encodeURIComponent(macroId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  getAppeals(status = "open", params = {}) {
    return this.request(`/api/appeals${buildQuery({ status, ...params })}`);
  },

  submitAppeal(payload) {
    return this.request("/api/appeals", {
      method: "POST",
      body: payload,
    });
  },

  updateAppeal(appealId, payload) {
    return this.request(`/api/appeals/${encodeURIComponent(appealId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  submitContact(payload) {
    return this.request("/api/contact", { method: "POST", body: payload });
  },
});
