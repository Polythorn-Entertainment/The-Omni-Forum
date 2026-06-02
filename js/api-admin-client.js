Object.assign(API, {
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
});
