Object.assign(API, {
  getHome() {
    return this.request("/api/home");
  },

  getSite() {
    return this.request("/api/site");
  },

  getAuthFeatures() {
    return this.request("/api/auth/features");
  },

  getMe() {
    return this.request("/api/me");
  },

  exportMyData() {
    return this.request("/api/me/export");
  },

  login(credentials) {
    return this.request("/api/login", { method: "POST", body: credentials });
  },

  register(credentials) {
    return this.request("/api/register", { method: "POST", body: credentials });
  },

  requestEmailPasswordReset(payload) {
    return this.request("/api/auth/email-reset", { method: "POST", body: payload });
  },

  completeEmailPasswordReset(payload) {
    return this.request("/api/auth/email-reset/complete", { method: "POST", body: payload });
  },

  logout() {
    return this.request("/api/logout", { method: "POST" });
  },

  updateProfile(payload) {
    return this.request("/api/me", { method: "PATCH", body: payload });
  },

  updatePassword(payload) {
    return this.request("/api/me/password", { method: "PATCH", body: payload });
  },

  revokeOtherSessions() {
    return this.request("/api/me/sessions/revoke-others", { method: "POST" });
  },

  getRecoveryCodes() {
    return this.request("/api/me/recovery-codes");
  },

  createRecoveryCodes(payload) {
    return this.request("/api/me/recovery-codes", { method: "POST", body: payload });
  },

  getLiveSnapshot(params = {}) {
    return this.request(`/api/live${buildQuery(params)}`);
  },

  getPlugins(params = {}) {
    return this.request(`/api/plugins${buildQuery(params)}`);
  },

  updatePlugin(pluginId, payload) {
    return this.request(`/api/plugins/${encodeURIComponent(pluginId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  getSearch(queryOrParams) {
    const params = typeof queryOrParams === "string" ? { q: queryOrParams } : (queryOrParams || {});
    return this.request(`/api/search${buildQuery(params)}`);
  },

  getNotifications(status = "all", kind = "all") {
    const params = typeof status === "object" ? status : { status, kind };
    return this.request(`/api/notifications${buildQuery(params)}`);
  },

  markNotificationRead(notificationId) {
    return this.request(`/api/notifications/${encodeURIComponent(notificationId)}`, {
      method: "PATCH",
    });
  },

  markNotificationsRead(payload = {}) {
    return this.request("/api/notifications/read-all", {
      method: "POST",
      body: payload,
    });
  },

  getMessages() {
    return this.request("/api/messages");
  },

  getMessageThread(threadId) {
    return this.request(`/api/messages/${encodeURIComponent(threadId)}`);
  },

  sendMessage(payload) {
    return this.request("/api/messages", { method: "POST", body: payload });
  },

  replyToMessage(threadId, payload) {
    return this.request(`/api/messages/${encodeURIComponent(threadId)}`, {
      method: "POST",
      body: payload,
    });
  },
});
