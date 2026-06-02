/* Settings page render helpers, theme preview helpers, lists, and draft recovery UI */

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

function settingsRestrictionLabel(user) {
  const moderation = user?.moderation || null;
  if (!moderation) return "Clear";
  if (moderation.isBanned) return "Banned";
  if (moderation.isTimedOut) return "Timed Out";
  if (moderation.isMuted) return "Muted";
  if (moderation.isShadowMuted) return "Shadow Muted";
  if (moderation.passwordResetRequired) return "Password Reset Required";
  return "Clear";
}

function dmPrivacyLabel(value) {
  return {
    everyone: "Everyone",
    members: "Members+",
    staff_only: "Staff Only",
    disabled: "Staff Only (No member DMs)",
  }[value] || "Everyone";
}

function renderSavedThreads(items = [], emptyCopy = "Nothing here yet.") {
  if (!items.length) {
    return `<div class="centered-message settings-empty-block">${escapeHtml(emptyCopy)}</div>`;
  }
  return `
    <div class="settings-thread-list">
      ${items.map((thread) => `
        <div class="settings-thread-card">
          <div>
            <div class="settings-thread-title">${escapeHtml(thread.title)}</div>
            <div class="settings-thread-meta">
              <span>${escapeHtml(thread.section.name)}</span>
              <span>${thread.savedAt ? escapeHtml(formatDateTime(thread.savedAt)) : escapeHtml(formatRelativeTime(thread.updatedAt))}</span>
            </div>
          </div>
          <div class="stack-actions">
            <button class="btn btn-ghost btn-sm" onclick="goToThread(${JSON.stringify(thread.id)})">Open</button>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderSessionList(sessions = []) {
  if (!sessions.length) {
    return `<div class="centered-message settings-empty-block">No recent sessions recorded yet.</div>`;
  }
  return `
    <div class="settings-session-list">
      ${sessions.map((session, index) => `
        <div class="settings-session-card">
          <div class="settings-session-head">
            <div class="settings-session-title">${escapeHtml(session.userAgent || "Unknown browser")}</div>
            <span class="badge ${session.active ? "badge-hot" : "badge-locked"}">${session.active ? (index === 0 ? "Current" : "Active") : "Expired"}</span>
          </div>
          <div class="detail-list settings-session-meta">
            <div><span>Seen</span><strong>${escapeHtml(formatDateTime(session.lastSeenAt || session.createdAt))}</strong></div>
            <div><span>IP</span><strong>${escapeHtml(session.lastSeenIp || session.ip || "Unknown")}</strong></div>
            <div><span>Started</span><strong>${escapeHtml(formatDateTime(session.createdAt))}</strong></div>
            <div><span>Expires</span><strong>${escapeHtml(formatDateTime(session.expiresAt))}</strong></div>
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAppealList(items = []) {
  if (!items.length) {
    return `<div class="centered-message settings-empty-block">No appeals submitted yet.</div>`;
  }
  return `
    <div class="moderation-history-list">
      ${items.map((item) => `
        <div class="moderation-history-card">
          <div class="moderation-history-head">
            <div>
              <div class="moderation-history-title">${item.status === "resolved" ? "Resolved Appeal" : "Open Appeal"}</div>
              <div class="moderation-history-meta">
                <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
                ${item.handledBy?.username ? `<span>${escapeHtml(item.handledBy.username)}</span>` : ""}
              </div>
            </div>
            <span class="badge ${item.status === "resolved" ? "badge-pin" : "badge-hot"}">${item.status === "resolved" ? "Resolved" : "Open"}</span>
          </div>
          <div class="moderation-history-copy">${escapeHtml(item.message)}</div>
          ${item.staffNote ? `<div class="tiny-copy">${escapeHtml(item.staffNote)}</div>` : ""}
        </div>
      `).join("")}
    </div>
  `;
}

function renderRelationshipList(items = []) {
  if (!items.length) {
    return `<div class="centered-message settings-empty-block">You are not ignoring or blocking anyone right now.</div>`;
  }
  return `
    <div class="settings-thread-list">
      ${items.map((item) => `
        <div class="settings-thread-card">
          <div>
            <div class="settings-thread-title">${escapeHtml(item.user?.username || "Member")}</div>
            <div class="settings-thread-meta">
              ${item.ignoreContent ? "<span>Ignoring posts</span>" : ""}
              ${item.blockDm ? "<span>Blocking DMs</span>" : ""}
              <span>${escapeHtml(formatRelativeTime(item.updatedAt))}</span>
            </div>
            ${item.user?.statusText ? `<div class="tiny-copy">${escapeHtml(item.user.statusText)}</div>` : ""}
          </div>
          <div class="stack-actions">
            <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.user?.id)})">Profile</button>
            ${item.ignoreContent ? `<button class="btn btn-outline btn-sm" onclick="updateSettingsRelationship(${JSON.stringify(item.user?.id)}, { ignoreContent: false, blockDm: ${item.blockDm ? "true" : "false"} })">Unignore</button>` : ""}
            ${item.blockDm ? `<button class="btn btn-outline btn-sm" onclick="updateSettingsRelationship(${JSON.stringify(item.user?.id)}, { ignoreContent: ${item.ignoreContent ? "true" : "false"}, blockDm: false })">Unblock DMs</button>` : ""}
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function draftRecoveryTarget(draft) {
  if (draft.scope === "new-thread") {
    return pageHref("section.html", { section: draft.id });
  }
  if (draft.scope === "thread-reply") {
    return pageHref("thread.html", { thread: draft.id });
  }
  return "";
}

function renderDraftRecoveryList() {
  const drafts = typeof listDrafts === "function" ? listDrafts() : [];
  if (!drafts.length) {
    return `<div class="centered-message settings-empty-block">No saved local drafts on this browser.</div>`;
  }
  return `
    <div class="settings-thread-list">
      ${drafts.slice(0, 12).map((draft) => {
        const href = draftRecoveryTarget(draft);
        const label = draft.scope === "new-thread" ? "Thread draft" : draft.scope === "thread-reply" ? "Reply draft" : "Draft";
        return `
          <div class="settings-thread-card">
            <div>
              <div class="settings-thread-title">${escapeHtml(draft.title || "Untitled draft")}</div>
              <div class="settings-thread-meta">
                <span>${escapeHtml(label)}</span>
                <span>${draft.savedAt ? escapeHtml(formatRelativeTime(draft.savedAt)) : "Saved locally"}</span>
              </div>
            </div>
            ${href ? `<a class="btn btn-ghost btn-sm" href="${escapeHtml(href)}">Recover</a>` : ""}
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function accentOptionMarkup(selected = "") {
  const palette = ["", "#00d4ff", "#7b5ea7", "#ff6b6b", "#ffd166", "#06d6a0", "#6b7a94"];
  return palette.map((value) => `
    <option value="${value}"${value === (selected || "") ? " selected" : ""}>${value || "Default accent"}</option>
  `).join("");
}

function siteThemeLabel(value) {
  return window.SITE_THEMES?.[value]?.label || window.SITE_THEMES?.midnight?.label || "Midnight Signal";
}

function siteThemeOptionMarkup(selected = "midnight") {
  return Object.entries(window.SITE_THEMES || {}).map(([id, theme]) => `
    <label
      class="settings-theme-option ${themePreviewClass(id)}${id === selected ? " active" : ""}"
    >
      <input
        type="radio"
        name="settingsSiteTheme"
        value="${escapeHtml(id)}"
        ${id === selected ? "checked" : ""}
        onchange="previewSettingsTheme(${serializeJsArg(id)})"
      >
      <span class="settings-theme-swatch" aria-hidden="true">
        <span class="settings-theme-swatch-bg"></span>
        <span class="settings-theme-swatch-line line-1"></span>
        <span class="settings-theme-swatch-line line-2"></span>
        <span class="settings-theme-swatch-dot dot-1"></span>
        <span class="settings-theme-swatch-dot dot-2"></span>
      </span>
      <span class="settings-theme-copy">
        <strong>${escapeHtml(theme.label)}</strong>
        <span>${escapeHtml(theme.description)}</span>
      </span>
    </label>
  `).join("");
}

function syncThemeSelectionState(selected) {
  document.querySelectorAll(".settings-theme-option").forEach((node) => {
    const input = node.querySelector("input[name='settingsSiteTheme']");
    node.classList.toggle("active", input?.value === selected);
  });
}

function previewSettingsTheme(themeId) {
  applySiteTheme(themeId, { storage: "ignore" });
  syncThemeSelectionState(themeId);
}
