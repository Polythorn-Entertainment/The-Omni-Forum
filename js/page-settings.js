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
      class="settings-theme-option${id === selected ? " active" : ""}"
      style="--theme-preview-bg:${theme.preview[0]};--theme-preview-accent:${theme.preview[1]};--theme-preview-accent2:${theme.preview[2]};--theme-preview-accent3:${theme.preview[3]};"
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

function renderSettingsContent() {
  const container = document.getElementById("settingsContent");
  if (!container) return;
  const user = Auth.getCurrentUser();
  document.title = "OmniForum — Settings";

  if (!user) {
    container.innerHTML = `
      <div class="page-section settings-guest-panel">
        <p class="hero-eyebrow">Account Center</p>
        <h1 class="thread-title">Sign in to manage your account</h1>
        <p class="muted-copy">Settings are only available to logged-in members. Once you sign in, this page becomes your account hub for profile edits, password changes, communication preferences, saved threads, sessions, and role-based tools.</p>
        <div class="settings-guest-actions">
          <button class="btn btn-primary" onclick="showLoginModal()">Log In</button>
          <button class="btn btn-ghost" onclick="showRegisterModal()">Create Account</button>
        </div>
      </div>
    `;
    return;
  }

  const role = DB.roles[user.role] || DB.roles.new;
  const xpData = DB.getXPForNextLevel(user.xp || 0);
  const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
  const moderation = user.moderation || null;
  const preferences = user.preferences || {
    siteTheme: "midnight",
    dmPrivacy: "everyone",
    notifyReplies: true,
    notifyLikes: true,
    notifyMentions: true,
    notifyDms: true,
  };
  const sessionAudit = user.recentSessions || user.sessionAudit || [];
  const library = user.library || { bookmarks: [], subscriptions: [] };
  const community = user.community || { signature: "", profileBadge: "", profileAccent: "" };

  const statusMarkup = moderation
    ? renderModerationStatus(moderation)
    : `
      <div class="moderation-status-stack">
        <div class="moderation-status-card ok settings-status-card">
          <div class="moderation-status-title">Account Clear</div>
          <div class="moderation-status-copy">There are no active restrictions on this account right now.</div>
        </div>
      </div>
    `;

  const staffSection = Auth.isStaff()
    ? `
      <div class="page-section">
        <div class="page-section-title">Staff Tools</div>
        <p class="muted-copy settings-section-copy">These controls are only visible to moderators and above.</p>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Reports Queue</div>
            <div class="settings-tool-copy">${fmtNum(user.reportCount || 0)} open user reports waiting for review.</div>
            <div class="stack-actions">
              <button class="btn btn-primary btn-sm" onclick="showReportsQueue()">Open Reports</button>
            </div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Staff Inbox</div>
            <div class="settings-tool-copy">${fmtNum(user.noticeCount || 0)} contact notices currently need staff attention.</div>
            <div class="stack-actions">
              <button class="btn btn-outline btn-sm" onclick="showStaffInbox()">Open Inbox</button>
            </div>
          </div>
        </div>
      </div>
    `
    : "";

  const adminSection = Auth.isAdmin()
    ? `
      <div class="page-section">
        <div class="page-section-title">Admin Controls</div>
        <p class="muted-copy settings-section-copy">Administrative tooling is intentionally hidden from moderators and below.</p>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Section Editor</div>
            <div class="settings-tool-copy">Create, reorder, and permission forum sections. This stays admin+ only.</div>
            <div class="stack-actions">
              <button class="btn btn-primary btn-sm" onclick="showSectionManager()">Manage Sections</button>
            </div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Admin Access</div>
            <div class="settings-tool-copy">You can moderate moderator-level accounts, issue recovery passwords, and manage section structure.</div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Operations</div>
            <div class="settings-tool-copy">Backups, health signals, logs, and orphaned media cleanup stay admin+ only.</div>
            <div class="stack-actions">
              <button class="btn btn-outline btn-sm" onclick="showAdminOpsModal()">Open Operations</button>
            </div>
          </div>
        </div>
      </div>
    `
    : "";

  const ownerSection = Auth.isOwner()
    ? `
      <div class="page-section">
        <div class="page-section-title">Owner Notes</div>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Highest Permission Tier</div>
            <div class="settings-tool-copy">Owner-level access can manage admins, change owner-owned areas, and bypass normal admin ceilings. Keep this account especially secure.</div>
          </div>
        </div>
      </div>
    `
    : "";

  container.innerHTML = `
    <div class="page-section legal-hero">
      <p class="hero-eyebrow">Account Center</p>
      <h1 class="thread-title">Settings for ${escapeHtml(user.username)}</h1>
      <p class="muted-copy">Manage your profile, privacy, saved threads, sessions, account status, and any role-based tools from one place.</p>
    </div>

    <div class="page-section">
      <div class="page-section-title">Account Overview <span>${roleBadge(user.role)}</span></div>
      <div class="settings-stat-grid">
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.posts || 0)}</div>
          <div class="settings-stat-label">Posts</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.threads || 0)}</div>
          <div class="settings-stat-label">Threads</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.xp || 0)}</div>
          <div class="settings-stat-label">XP</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.likesReceived || 0)}</div>
          <div class="settings-stat-label">Likes Received</div>
        </div>
      </div>
      <div class="xp-bar-wrap" style="margin-top:18px;">
        <div class="xp-label">
          <span>${escapeHtml(xpData.label)} Progress</span>
          <span>${progress}%</span>
        </div>
        <div class="xp-bar"><div class="xp-fill" style="width:${progress}%"></div></div>
      </div>
      <div class="detail-list">
        <div><span>Role</span><strong>${escapeHtml(role.label)}</strong></div>
        <div><span>Member Since</span><strong>${escapeHtml(formatDate(user.joined))}</strong></div>
        <div><span>Status</span><strong>${user.online ? "Online" : "Offline"}</strong></div>
        <div><span>Restrictions</span><strong>${escapeHtml(settingsRestrictionLabel(user))}</strong></div>
        <div><span>Unread Alerts</span><strong>${fmtNum(user.notificationCount || 0)}</strong></div>
        <div><span>Unread Messages</span><strong>${fmtNum(user.messageCount || 0)}</strong></div>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Profile</div>
      <p class="muted-copy settings-section-copy">Update the public details other members see when they open your profile.</p>
      <div class="form-error" id="settingsProfileError"></div>
      <div class="settings-profile-shell">
        <div class="settings-avatar-panel">
          ${makeAvatar(user, "settings")}
          <div class="tiny-copy">Visible in posts, member cards, DMs, and the leaderboard.</div>
        </div>
        <div class="settings-form-grid">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input class="form-input" id="settingsUsername" maxlength="24" value="${escapeHtml(user.username || "")}" placeholder="Username">
            <div class="form-hint">3-24 characters using letters, numbers, _ or -.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <input class="form-input" value="${escapeHtml(role.label)}" disabled>
            <div class="form-hint">Role changes stay staff-controlled.</div>
          </div>
          <div class="form-group full">
            <label class="form-label">Profile Picture</label>
            <input class="form-input" id="settingsAvatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp">
            <div class="form-hint">PNG, JPG, GIF, or WEBP. Keep it under ${Math.round(UPLOAD_LIMITS.avatarBytes / (1024 * 1024))}MB.</div>
            ${user.avatarUrl ? `
              <label class="checkbox-row settings-checkbox-row">
                <input type="checkbox" id="settingsRemoveAvatar">
                <span>Remove the current profile picture</span>
              </label>
            ` : ""}
          </div>
          <div class="form-group full">
            <label class="form-label">Bio</label>
            <textarea class="form-textarea" id="settingsBio" maxlength="280" placeholder="Tell the forum a little about yourself.">${escapeHtml(user.bio || "")}</textarea>
            <div class="form-hint">Up to 280 characters.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Profile Badge</label>
            <input class="form-input" id="settingsProfileBadge" maxlength="32" value="${escapeHtml(community.profileBadge || "")}" placeholder="Builder">
            <div class="form-hint">Optional short badge shown on your profile.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Accent Color</label>
            <select class="form-input" id="settingsProfileAccent">${accentOptionMarkup(community.profileAccent || "")}</select>
            <div class="form-hint">A subtle accent used on your profile card.</div>
          </div>
          <div class="form-group full">
            <label class="form-label">Signature</label>
            <textarea class="form-textarea" id="settingsSignature" maxlength="240" placeholder="Appears below your posts. Supports the same markdown / BBCode as the post composer.">${escapeHtml(community.signature || "")}</textarea>
            <div class="form-hint">Great for a short intro, favorite quote, or project link.</div>
          </div>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="showProfile(${JSON.stringify(user.id)})">Preview Profile</button>
        <button class="btn btn-primary" onclick="saveSettingsProfile()">Save Profile</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Appearance</div>
      <p class="muted-copy settings-section-copy">Choose a full-site color scheme. Clicking an option previews it immediately; saving makes it your default on every page.</p>
      <div class="form-error" id="settingsThemeError"></div>
      <div class="settings-theme-grid">
        ${siteThemeOptionMarkup(preferences.siteTheme || "midnight")}
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsTheme()">Save Theme</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Communication & Privacy</div>
      <p class="muted-copy settings-section-copy">Decide who can start DMs with you and which activity creates alerts.</p>
      <div class="form-error" id="settingsPreferencesError"></div>
      <div class="settings-form-grid">
        <div class="form-group full">
          <label class="form-label">Direct Message Privacy</label>
          <select class="form-input" id="settingsDmPrivacy">
            <option value="everyone"${preferences.dmPrivacy === "everyone" ? " selected" : ""}>Everyone</option>
            <option value="members"${preferences.dmPrivacy === "members" ? " selected" : ""}>Members and Above</option>
            <option value="staff_only"${preferences.dmPrivacy === "staff_only" ? " selected" : ""}>Staff Only</option>
            <option value="disabled"${preferences.dmPrivacy === "disabled" ? " selected" : ""}>Disable Member DMs</option>
          </select>
          <div class="form-hint">Staff can still reach you for moderation or safety reasons.</div>
        </div>
        <div class="form-group full">
          <label class="form-label">Notification Preferences</label>
          <div class="checkbox-stack">
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyReplies"${preferences.notifyReplies ? " checked" : ""}> <span>Replies in threads you participate in or follow</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyLikes"${preferences.notifyLikes ? " checked" : ""}> <span>Likes on your posts</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyMentions"${preferences.notifyMentions ? " checked" : ""}> <span>@mentions</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyDms"${preferences.notifyDms ? " checked" : ""}> <span>Direct messages</span></label>
          </div>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsPreferences()">Save Preferences</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Saved Threads & Following</div>
      <p class="muted-copy settings-section-copy">Bookmarks are private. Followed threads continue to send reply alerts when your preferences allow it.</p>
      <div class="settings-library-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Bookmarked Threads</div>
          <div class="settings-tool-copy">${fmtNum(library.bookmarks?.length || 0)} recent saved thread${(library.bookmarks?.length || 0) === 1 ? "" : "s"}.</div>
          ${renderSavedThreads(library.bookmarks || [], "You have not bookmarked any threads yet.")}
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Followed Threads</div>
          <div class="settings-tool-copy">${fmtNum(library.subscriptions?.length || 0)} recent followed thread${(library.subscriptions?.length || 0) === 1 ? "" : "s"}.</div>
          ${renderSavedThreads(library.subscriptions || [], "You are not following any threads yet.")}
        </div>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Security</div>
      <p class="muted-copy settings-section-copy">Use a strong password you do not reuse anywhere else.</p>
      <div class="form-error" id="settingsPasswordError"></div>
      ${user.mustResetPassword ? `
        <div class="moderation-status-card info settings-status-card">
          <div class="moderation-status-title">Password Reset Required</div>
          <div class="moderation-status-copy">This account is currently using a temporary password. Set a new permanent one here before continuing normal forum use.</div>
        </div>
      ` : ""}
      <div class="settings-form-grid">
        ${user.mustResetPassword ? "" : `
          <div class="form-group">
            <label class="form-label">Current Password</label>
            <input class="form-input" id="settingsCurrentPassword" type="password" autocomplete="current-password" placeholder="Current password">
          </div>
        `}
        <div class="form-group">
          <label class="form-label">New Password</label>
          <input class="form-input" id="settingsNewPassword" type="password" autocomplete="new-password" placeholder="New password">
        </div>
        <div class="form-group">
          <label class="form-label">Confirm New Password</label>
          <input class="form-input" id="settingsConfirmPassword" type="password" autocomplete="new-password" placeholder="Confirm new password">
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsPassword()">Update Password</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Sessions</div>
      <p class="muted-copy settings-section-copy">Review the latest places this account was active and sign out any other sessions.</p>
      <div class="form-error" id="settingsSessionsError"></div>
      ${renderSessionList(sessionAudit)}
      <div class="form-actions">
        <button class="btn btn-outline" onclick="revokeSettingsSessions()">Sign Out Other Sessions</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Account Status</div>
      <p class="muted-copy settings-section-copy">If staff actions affect your account, they will surface here.</p>
      ${statusMarkup}
    </div>

    ${(user.appeals?.length || moderation?.isBanned || moderation?.isTimedOut || moderation?.isMuted) ? `
      <div class="page-section">
        <div class="page-section-title">Appeals</div>
        <p class="muted-copy settings-section-copy">Use appeals for bans, timeouts, or mutes that you believe should be reviewed.</p>
        <div class="form-actions">
          <button class="btn btn-primary" onclick="showAppealsQueue('all')">Open Appeals</button>
        </div>
        ${renderAppealList(user.appeals || [])}
      </div>
    ` : ""}

    ${staffSection}
    ${adminSection}
    ${ownerSection}

    <div class="page-section">
      <div class="page-section-title">Policy & Help</div>
      <div class="settings-link-grid">
        <div class="settings-link-card">
          <a href="rules.html">Forum Rules</a>
          <div class="settings-tool-copy">Review the community standards that govern posting and moderation.</div>
        </div>
        <div class="settings-link-card">
          <a href="privacy.html">Privacy Policy</a>
          <div class="settings-tool-copy">See what the forum stores, how sessions work, and what staff can review.</div>
        </div>
        <div class="settings-link-card">
          <a href="contact.html">Contact Staff</a>
          <div class="settings-tool-copy">Reach moderators/admins for support, account issues, or policy questions.</div>
        </div>
      </div>
    </div>
  `;
}

function renderSettingsSidebar() {
  const container = document.getElementById("settingsSidebar");
  if (!container) return;
  const user = Auth.getCurrentUser();

  if (!user) {
    container.innerHTML = `
      <div class="sidebar-section">
        <h3 class="sidebar-title">Why Settings</h3>
        <ul class="sidebar-stats">
          <li><span>Profile edits</span><strong>Members only</strong></li>
          <li><span>Password changes</span><strong>Secure</strong></li>
          <li><span>Staff tools</span><strong>Role-gated</strong></li>
        </ul>
      </div>
    `;
    return;
  }

  const permissionItems = [
    { label: "Read access", value: "Based on role" },
    { label: "Post access", value: "Section-based" },
    { label: "Theme", value: siteThemeLabel(user.preferences?.siteTheme || "midnight") },
    { label: "DM privacy", value: dmPrivacyLabel(user.preferences?.dmPrivacy || "everyone") },
    { label: "Moderation tools", value: Auth.isStaff() ? "Granted" : "Hidden" },
    { label: "Section editor", value: Auth.isAdmin() ? "Granted" : "Hidden" },
    { label: "Operations", value: Auth.isAdmin() ? "Granted" : "Hidden" },
  ];

  container.innerHTML = `
    <div class="sidebar-section">
      <h3 class="sidebar-title">Live Signals</h3>
      <ul class="sidebar-stats">
        <li><span>Alerts</span><strong>${fmtNum(user.notificationCount || 0)}</strong></li>
        <li><span>Messages</span><strong>${fmtNum(user.messageCount || 0)}</strong></li>
        ${Auth.isStaff() ? `<li><span>Open Reports</span><strong>${fmtNum(user.reportCount || 0)}</strong></li>` : ""}
        ${Auth.isStaff() ? `<li><span>Open Appeals</span><strong>${fmtNum(user.appealCount || 0)}</strong></li>` : ""}
        ${Auth.isStaff() ? `<li><span>Staff Notices</span><strong>${fmtNum(user.noticeCount || 0)}</strong></li>` : ""}
        <li><span>Public Role</span><strong>${escapeHtml(DB.roles[user.role]?.label || "Member")}</strong></li>
      </ul>
    </div>
    <div class="sidebar-section">
      <h3 class="sidebar-title">Your Access</h3>
      <ul class="sidebar-stats settings-permissions-list">
        ${permissionItems.map((item) => `<li><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></li>`).join("")}
      </ul>
    </div>
    <div class="sidebar-section">
      <h3 class="sidebar-title">Quick Links</h3>
      <div class="stack-actions">
        <button class="btn btn-outline btn-sm" onclick="showNotifications()">Alerts</button>
        <button class="btn btn-ghost btn-sm" onclick="showMessages()">Messages</button>
        ${Auth.isStaff() ? '<button class="btn btn-ghost btn-sm" onclick="showReportsQueue()">Reports</button>' : ""}
        ${(user.moderation?.isBanned || user.moderation?.isTimedOut || user.moderation?.isMuted || (user.appeals?.length || 0)) ? '<button class="btn btn-ghost btn-sm" onclick="showAppealsQueue(\'all\')">Appeals</button>' : ""}
        ${Auth.isStaff() ? '<button class="btn btn-ghost btn-sm" onclick="showStaffInbox()">Inbox</button>' : ""}
        ${Auth.isAdmin() ? '<button class="btn btn-ghost btn-sm" onclick="showAdminOpsModal()">Ops</button>' : ""}
      </div>
    </div>
  `;
}

async function refreshCurrentPage() {
  try {
    await Auth.refresh();
    const viewer = Auth.getCurrentUser();
    if (viewer?.id) {
      const data = await API.getUser(viewer.id);
      Auth.setCurrentUser(data.user || viewer);
    }
  } catch {
    Auth.setCurrentUser(null);
  }
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();
  renderSettingsContent();
  renderSettingsSidebar();
}

async function saveSettingsProfile() {
  const error = document.getElementById("settingsProfileError");
  const username = document.getElementById("settingsUsername")?.value?.trim() || "";
  const bio = document.getElementById("settingsBio")?.value || "";
  const profileBadge = document.getElementById("settingsProfileBadge")?.value?.trim() || "";
  const profileAccent = document.getElementById("settingsProfileAccent")?.value || "";
  const signature = document.getElementById("settingsSignature")?.value || "";
  const avatarInput = document.getElementById("settingsAvatarInput");
  const removeAvatar = Boolean(document.getElementById("settingsRemoveAvatar")?.checked);
  if (error) error.classList.remove("visible");

  try {
    const avatarUpload = await readSingleImageUpload(avatarInput?.files, {
      maxBytes: UPLOAD_LIMITS.avatarBytes,
      field: "Profile picture",
    });
    const payload = { username, bio, profileBadge, profileAccent, signature };
    if (avatarUpload) {
      payload.avatarUpload = avatarUpload;
    } else if (removeAvatar) {
      payload.removeAvatar = true;
    }
    const data = await API.updateProfile(payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Profile updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your profile settings.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsPreferences() {
  const error = document.getElementById("settingsPreferencesError");
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({
      dmPrivacy: document.getElementById("settingsDmPrivacy")?.value || "everyone",
      notifyReplies: Boolean(document.getElementById("settingsNotifyReplies")?.checked),
      notifyLikes: Boolean(document.getElementById("settingsNotifyLikes")?.checked),
      notifyMentions: Boolean(document.getElementById("settingsNotifyMentions")?.checked),
      notifyDms: Boolean(document.getElementById("settingsNotifyDms")?.checked),
    });
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Preferences updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your communication preferences.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsTheme() {
  const error = document.getElementById("settingsThemeError");
  const selected = document.querySelector("input[name='settingsSiteTheme']:checked")?.value || "midnight";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({ siteTheme: selected });
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Theme updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your theme.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsPassword() {
  const error = document.getElementById("settingsPasswordError");
  const currentPassword = document.getElementById("settingsCurrentPassword")?.value || "";
  const newPassword = document.getElementById("settingsNewPassword")?.value || "";
  const confirmPassword = document.getElementById("settingsConfirmPassword")?.value || "";
  if (error) error.classList.remove("visible");

  if (newPassword !== confirmPassword) {
    if (error) {
      error.textContent = "New passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const payload = { newPassword };
    if (!Auth.mustResetPassword()) {
      payload.currentPassword = currentPassword;
    }
    const data = await API.updatePassword(payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Password updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update your password.";
      error.classList.add("visible");
    }
  }
}

async function revokeSettingsSessions() {
  const error = document.getElementById("settingsSessionsError");
  if (error) error.classList.remove("visible");

  try {
    const data = await API.revokeOtherSessions();
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Other sessions signed out.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not revoke your other sessions.";
      error.classList.add("visible");
    }
  }
}

window.refreshCurrentPage = refreshCurrentPage;
window.saveSettingsProfile = saveSettingsProfile;
window.saveSettingsPreferences = saveSettingsPreferences;
window.saveSettingsTheme = saveSettingsTheme;
window.saveSettingsPassword = saveSettingsPassword;
window.revokeSettingsSessions = revokeSettingsSessions;
window.previewSettingsTheme = previewSettingsTheme;
