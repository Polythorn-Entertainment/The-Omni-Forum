function closeNavMenu() {
  if (!navMenuState.open) return;
  navMenuState.open = false;
  renderNavActions();
}

function toggleNavMenu(event) {
  event?.stopPropagation();
  navMenuState.open = !navMenuState.open;
  renderNavActions();
}

function goToSettingsPage() {
  closeNavMenu();
  window.location.href = settingsPageHref();
}

document.addEventListener("click", (event) => {
  if (!navMenuState.open) return;
  if (event.target?.closest(".nav-menu")) return;
  closeNavMenu();
});

function renderNavActions() {
  const container = document.getElementById("navActions");
  if (!container) return;
  const user = Auth.getCurrentUser();
  const isOpen = navMenuState.open;
  if (user) {
    const notificationCount = Number(user.notificationCount || 0);
    const messageCount = Number(user.messageCount || 0);
        const reportCount = Number(user.reportCount || 0);
        const noticeCount = Number(user.noticeCount || 0);
        const appealCount = Number(user.appealCount || 0);
        const registrationCount = Number(user.registrationCount || 0);
    const attentionCount = navAttentionCount(user);
    const attentionBadge = attentionCount ? `<span class="notice-pill">${attentionCount}</span>` : "";
    const staffTools = Auth.isStaff()
      ? `
        <div class="nav-menu-section-label">Staff</div>
        <button class="nav-menu-item" onclick="closeNavMenu(); showReportsQueue()">
          <span class="nav-menu-item-main">Reports Queue</span>
          ${reportCount ? `<span class="nav-menu-item-badge">${reportCount}</span>` : '<span class="nav-menu-item-meta">Open</span>'}
        </button>
        <button class="nav-menu-item" onclick="closeNavMenu(); showAppealsQueue()">
          <span class="nav-menu-item-main">Appeals</span>
          ${appealCount ? `<span class="nav-menu-item-badge">${appealCount}</span>` : '<span class="nav-menu-item-meta">Open</span>'}
        </button>
        <button class="nav-menu-item" onclick="closeNavMenu(); showStaffInbox()">
          <span class="nav-menu-item-main">Staff Inbox</span>
          ${noticeCount ? `<span class="nav-menu-item-badge">${noticeCount}</span>` : '<span class="nav-menu-item-meta">Open</span>'}
        </button>
      `
      : "";
    const adminTools = Auth.isAdmin()
      ? `
        <div class="nav-menu-section-label">Admin</div>
        <button class="nav-menu-item" onclick="closeNavMenu(); showSectionManager()">
          <span class="nav-menu-item-main">Section Editor</span>
          <span class="nav-menu-item-meta">Admin+</span>
        </button>
            <button class="nav-menu-item" onclick="closeNavMenu(); showAdminOpsModal()">
              <span class="nav-menu-item-main">Operations</span>
              ${registrationCount ? `<span class="nav-menu-item-badge">${registrationCount}</span>` : '<span class="nav-menu-item-meta">Health</span>'}
            </button>
      `
      : "";
    container.innerHTML = `
      <div class="nav-menu ${isOpen ? "open" : ""}">
        <button class="nav-menu-trigger ${attentionCount ? "has-alert" : ""}" onclick="toggleNavMenu(event)" aria-expanded="${isOpen ? "true" : "false"}" aria-haspopup="menu" aria-label="Open account menu">
          ${makeAvatar(user, "xs")}
          <span class="nav-menu-label">
            <span class="nav-menu-username">${escapeHtml(user.username)}</span>
            <span class="nav-menu-role">${escapeHtml(DB.roles[user.role]?.label || "Member")}</span>
          </span>
          ${attentionBadge}
          <span class="nav-menu-caret">${isOpen ? "▴" : "▾"}</span>
        </button>
        ${isOpen ? `
          <div class="nav-menu-panel">
            <div class="nav-menu-header">
              <div class="nav-menu-header-title">Quick Menu</div>
              <div class="nav-menu-header-copy">${user.online ? "Online now" : "Signed in"}</div>
            </div>
            <div class="nav-menu-section-label">Forum</div>
            <button class="nav-menu-item" onclick="closeNavMenu(); showSearchModal()">
              <span class="nav-menu-item-main">Search</span>
              <span class="nav-menu-item-meta">/</span>
            </button>
            <button class="nav-menu-item" onclick="closeNavMenu(); showNotifications()">
              <span class="nav-menu-item-main">Alerts</span>
              ${notificationCount ? `<span class="nav-menu-item-badge">${notificationCount}</span>` : '<span class="nav-menu-item-meta">All clear</span>'}
            </button>
            <button class="nav-menu-item" onclick="closeNavMenu(); showMessages()">
              <span class="nav-menu-item-main">Messages</span>
              ${messageCount ? `<span class="nav-menu-item-badge">${messageCount}</span>` : '<span class="nav-menu-item-meta">Inbox</span>'}
            </button>
            <button class="nav-menu-item" onclick="closeNavMenu(); showProfile(${JSON.stringify(user.id)})">
              <span class="nav-menu-item-main">Profile</span>
              <span class="nav-menu-item-meta">View</span>
            </button>
            <a class="nav-menu-item nav-menu-link" href="${escapeHtml(settingsPageHref())}" onclick="closeNavMenu()">
              <span class="nav-menu-item-main">Settings</span>
              <span class="nav-menu-item-meta">Account</span>
            </a>
            ${staffTools}
            ${adminTools}
            <div class="nav-menu-divider"></div>
            <button class="nav-menu-item nav-menu-item-danger" onclick="closeNavMenu(); logoutUser()">
              <span class="nav-menu-item-main">Log Out</span>
              <span class="nav-menu-item-meta">Session</span>
            </button>
          </div>
        ` : ""}
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="nav-menu ${isOpen ? "open" : ""}">
      <button class="nav-menu-trigger" onclick="toggleNavMenu(event)" aria-expanded="${isOpen ? "true" : "false"}" aria-haspopup="menu" aria-label="Open account menu">
        <span class="nav-menu-label nav-menu-label-guest">
          <span class="nav-menu-username">Menu</span>
          <span class="nav-menu-role">Explore OmniForum</span>
        </span>
        <span class="nav-menu-caret">${isOpen ? "▴" : "▾"}</span>
      </button>
      ${isOpen ? `
        <div class="nav-menu-panel">
          <div class="nav-menu-header">
            <div class="nav-menu-header-title">Welcome</div>
            <div class="nav-menu-header-copy">Browse the forum or sign in to join the conversation.</div>
          </div>
          <div class="nav-menu-section-label">Start Here</div>
          <button class="nav-menu-item" onclick="closeNavMenu(); showSearchModal()">
            <span class="nav-menu-item-main">Search</span>
            <span class="nav-menu-item-meta">Browse</span>
          </button>
          <button class="nav-menu-item" onclick="closeNavMenu(); showLoginModal()">
            <span class="nav-menu-item-main">Log In</span>
            <span class="nav-menu-item-meta">Member access</span>
          </button>
          <button class="nav-menu-item" onclick="closeNavMenu(); showRegisterModal()">
            <span class="nav-menu-item-main">Sign Up</span>
            <span class="nav-menu-item-meta">Create account</span>
          </button>
        </div>
      ` : ""}
    </div>
  `;
}
