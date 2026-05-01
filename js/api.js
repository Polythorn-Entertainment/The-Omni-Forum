class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null && item !== "") {
          query.append(key, item);
        }
      });
      return;
    }
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  return query.toString() ? `?${query.toString()}` : "";
}

const API = {
  async request(path, options = {}) {
    const config = {
      method: options.method || "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    };

    if (options.body !== undefined) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(options.body);
    }

    if (!["GET", "HEAD", "OPTIONS"].includes(String(config.method).toUpperCase())) {
      const csrfToken = window.Auth?.getCurrentUser?.()?.csrfToken;
      if (csrfToken) {
        config.headers["X-CSRF-Token"] = csrfToken;
      }
    }

    const response = await fetch(path, config);
    const text = await response.text();
    let payload = {};

    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { error: "The server returned invalid JSON." };
      }
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "roles") && window.DB) {
      DB.setRoles(payload.roles);
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "currentUser") && window.Auth) {
      Auth.setCurrentUser(payload.currentUser);
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "site") && typeof window.applySiteConfig === "function") {
      window.applySiteConfig(payload.site);
    }

    if (!response.ok) {
      throw new ApiError(payload?.error || `Request failed with status ${response.status}.`, response.status, payload);
    }

    return payload;
  },

  getHome() {
    return this.request("/api/home");
  },

  getSite() {
    return this.request("/api/site");
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

  createSection(payload) {
    return this.request("/api/sections", { method: "POST", body: payload });
  },

  updateSection(sectionId, payload) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteSection(sectionId) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "DELETE",
    });
  },

  getUsers(params = {}) {
    return this.request(`/api/users${buildQuery(params)}`);
  },

  getUser(userId) {
    return this.request(`/api/users/${encodeURIComponent(userId)}`);
  },

  updateUserRelationship(userId, payload) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/relationship`, {
      method: "POST",
      body: payload,
    });
  },

  updateUserRole(userId, role) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/role`, {
      method: "PATCH",
      body: { role },
    });
  },

  moderateUser(userId, payload) {
    return this.request(`/api/users/${encodeURIComponent(userId)}/moderation`, {
      method: "POST",
      body: payload,
    });
  },

  getSection(sectionId, params = {}) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}${buildQuery(params)}`);
  },

  createThread(sectionId, payload) {
    return this.request(`/api/sections/${encodeURIComponent(sectionId)}`, {
      method: "POST",
      body: payload,
    });
  },

  getThread(threadId, params = {}) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}${buildQuery(params)}`);
  },

  updateThread(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  deleteThread(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}`, {
      method: "DELETE",
    });
  },

  createPost(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/posts`, {
      method: "POST",
      body: payload,
    });
  },

  updatePost(postId, payload) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  getPostHistory(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`);
  },

  deletePost(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}`, {
      method: "DELETE",
    });
  },

  toggleLike(postId) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}/like`, {
      method: "POST",
    });
  },

  toggleReaction(postId, emoji) {
    return this.request(`/api/posts/${encodeURIComponent(postId)}/reactions`, {
      method: "POST",
      body: { emoji },
    });
  },

  toggleThreadBookmark(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/bookmark`, {
      method: "POST",
    });
  },

  toggleThreadSubscription(threadId) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/subscription`, {
      method: "POST",
    });
  },

  splitThread(threadId, payload) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/split`, {
      method: "POST",
      body: payload,
    });
  },

  voteThreadPoll(threadId, optionIds) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/poll`, {
      method: "POST",
      body: { optionIds },
    });
  },

  getAdminHealth() {
    return this.request("/api/admin/health");
  },

  getAdminTrash(limit = 60) {
    return this.request(`/api/admin/trash${buildQuery({ limit })}`);
  },

  createBackup() {
    return this.request("/api/admin/backup", {
      method: "POST",
    });
  },

  getBackupGuide(filename) {
    return this.request(`/api/admin/backups/guide${buildQuery({ file: filename })}`);
  },

  getAdminLogs() {
    return this.request("/api/admin/logs");
  },

  getAdminAudit(params = {}) {
    return this.request(`/api/admin/audit${buildQuery(params)}`);
  },

  getAdminSiteSettings() {
    return this.request("/api/admin/site-settings");
  },

  updateAdminSiteSettings(payload) {
    return this.request("/api/admin/site-settings", {
      method: "PATCH",
      body: payload,
    });
  },

  getAdminExport(params = {}) {
    return this.request(`/api/admin/export${buildQuery(params)}`);
  },

  previewAdminImport(payload) {
    return this.request("/api/admin/import-preview", {
      method: "POST",
      body: payload,
    });
  },

  getAdminRegistration() {
    return this.request("/api/admin/registration");
  },

  updateRegistrationSettings(payload) {
    return this.request("/api/admin/registration/settings", {
      method: "PATCH",
      body: payload,
    });
  },

  createInvite(payload) {
    return this.request("/api/admin/invites", {
      method: "POST",
      body: payload,
    });
  },

  updateInvite(inviteId, payload) {
    return this.request(`/api/admin/invites/${encodeURIComponent(inviteId)}`, {
      method: "PATCH",
      body: payload,
    });
  },

  reviewRegistration(userId, payload) {
    return this.request(`/api/admin/registrations/${encodeURIComponent(userId)}/review`, {
      method: "POST",
      body: payload,
    });
  },

  cleanupMedia() {
    return this.request("/api/admin/media-cleanup", {
      method: "POST",
    });
  },

  restoreAdminTrash(payload) {
    return this.request("/api/admin/trash/restore", {
      method: "POST",
      body: payload,
    });
  },

  getLeaderboard(metric = "xp", params = {}) {
    return this.request(`/api/leaderboard${buildQuery({ metric, ...params })}`);
  },

  getNotices(status = "open") {
    return this.request(`/api/notices?status=${encodeURIComponent(status)}`);
  },

  updateNotice(noticeId, payload) {
    return this.request(`/api/notices/contact/${encodeURIComponent(noticeId)}`, {
      method: "PATCH",
      body: payload,
    });
  },
};

window.API = API;
window.ApiError = ApiError;
