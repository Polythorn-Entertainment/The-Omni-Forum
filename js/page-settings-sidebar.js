/* Settings sidebar and page refresh flow */

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
    { label: "Ignored members", value: fmtNum((user.relationships || []).filter((item) => item.ignoreContent).length) },
    { label: "Blocked DMs", value: fmtNum((user.relationships || []).filter((item) => item.blockDm).length) },
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
  setPageMetadata({
    title: "OmniForum — Settings",
    description: "Manage your OmniForum account, profile, privacy, notifications, sessions, and appearance preferences.",
    canonicalPath: `${window.location.pathname}${window.location.search || ""}`,
    type: "website",
    noindex: true,
  });
}
