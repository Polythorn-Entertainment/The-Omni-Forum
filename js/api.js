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

    if (!response.ok) {
      throw new ApiError(payload?.error || `Request failed with status ${response.status}.`, response.status, payload);
    }

    return payload;
  },

  getHome() {
    return this.request("/api/home");
  },

  getMe() {
    return this.request("/api/me");
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

  getSearch(queryOrParams) {
    const params = typeof queryOrParams === "string" ? { q: queryOrParams } : (queryOrParams || {});
    return this.request(`/api/search${buildQuery(params)}`);
  },

  getNotifications(status = "all") {
    return this.request(`/api/notifications?status=${encodeURIComponent(status)}`);
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

  voteThreadPoll(threadId, optionIds) {
    return this.request(`/api/threads/${encodeURIComponent(threadId)}/poll`, {
      method: "POST",
      body: { optionIds },
    });
  },

  getAdminHealth() {
    return this.request("/api/admin/health");
  },

  createBackup() {
    return this.request("/api/admin/backup", {
      method: "POST",
    });
  },

  getAdminLogs() {
    return this.request("/api/admin/logs");
  },

  cleanupMedia() {
    return this.request("/api/admin/media-cleanup", {
      method: "POST",
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
