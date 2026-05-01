function toast(message, type = "info", duration = 3500) {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const icons = { success: "✓", error: "✕", info: "◈" };
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.innerHTML = `<span>${icons[type] || "◈"}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(node);
  window.setTimeout(() => {
    node.style.opacity = "0";
    node.style.transition = "opacity 0.3s";
    window.setTimeout(() => node.remove(), 300);
  }, duration);
}

async function copyTextValue(value, label = "Value") {
  try {
    await navigator.clipboard.writeText(String(value || ""));
    toast(`${label} copied.`, "success");
  } catch {
    toast(`Could not copy that ${label.toLowerCase()}.`, "error");
  }
}

const modalState = {
  dismissible: true,
  lastFocus: null,
};

function openModal(html, options = {}) {
  const modal = document.getElementById("modal");
  const overlay = document.getElementById("modalOverlay");
  if (!modal || !overlay) return;
  modalState.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  modal.classList.remove("modal-lg");
  modal.classList.remove("modal-xl");
  if (options.size === "lg") modal.classList.add("modal-lg");
  if (options.size === "xl") modal.classList.add("modal-xl");
  modalState.dismissible = options.dismissible !== false;
  modal.innerHTML = html;
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  overlay.classList.remove("hidden");
  window.setTimeout(() => {
    const focusTarget = modal.querySelector("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
    focusTarget?.focus();
  }, 0);
}

function closeModal(event, force = false) {
  const overlay = document.getElementById("modalOverlay");
  if (!overlay) return;
  if (!modalState.dismissible && !force) return;
  if (!event || event.target === overlay) {
    modalState.dismissible = true;
    overlay.classList.add("hidden");
    modalState.lastFocus?.focus?.();
    modalState.lastFocus = null;
  }
}

function applyViewerPresentationPreferences(user) {
  const root = document.documentElement;
  root.dataset.compactPosts = user?.preferences?.compactPostLayout ? "1" : "0";
  root.dataset.hideIgnoredContent = user?.preferences?.hideIgnoredContent === false ? "0" : "1";
  root.dataset.blurSensitiveMedia = user?.preferences?.blurSensitiveMedia === false ? "0" : "1";
}

let activeSiteConfig = {
  siteName: "OmniForum",
  logoText: "OmniForum",
  logoMark: "◈",
  heroEyebrow: "Welcome to",
  heroTitle: "OmniForum",
  heroSubtitle: "A community built for thinkers, creators, and builders.",
  footerCopy: "Community Forum · Built with passion",
  defaultTheme: "midnight",
  footerLinks: [
    { label: "Rules", url: "/pages/rules.html" },
    { label: "Privacy", url: "/pages/privacy.html" },
    { label: "Contact", url: "/pages/contact.html" },
  ],
};

function heroTitleMarkup(title) {
  const cleanTitle = String(title || "OmniForum");
  const forumIndex = cleanTitle.toLowerCase().lastIndexOf("forum");
  if (forumIndex > 0) {
    return `${escapeHtml(cleanTitle.slice(0, forumIndex))}<span class="title-accent">${escapeHtml(cleanTitle.slice(forumIndex))}</span>`;
  }
  return escapeHtml(cleanTitle);
}

function getSiteDefaultTheme() {
  return resolveSiteTheme(activeSiteConfig.defaultTheme || "midnight");
}

function applySiteConfig(site = {}) {
  activeSiteConfig = { ...activeSiteConfig, ...(site || {}) };
  const logoMark = activeSiteConfig.logoMark || "◈";
  const logoText = activeSiteConfig.logoText || activeSiteConfig.siteName || "OmniForum";
  document.querySelectorAll(".logo-mark").forEach((node) => {
    node.textContent = logoMark;
  });
  document.querySelectorAll(".logo-text:not(.footer-logo)").forEach((node) => {
    node.textContent = logoText;
  });
  document.querySelectorAll(".footer-logo").forEach((node) => {
    node.textContent = `${logoMark} ${logoText}`;
  });
  document.querySelectorAll(".hero-eyebrow").forEach((node) => {
    if (node.closest(".forum-hero")) node.textContent = activeSiteConfig.heroEyebrow || "Welcome to";
  });
  document.querySelectorAll(".hero-title").forEach((node) => {
    node.innerHTML = heroTitleMarkup(activeSiteConfig.heroTitle || logoText);
  });
  document.querySelectorAll(".hero-sub").forEach((node) => {
    node.textContent = activeSiteConfig.heroSubtitle || "";
  });
  document.querySelectorAll(".footer-copy").forEach((node) => {
    const year = node.querySelector("#footerYear")?.textContent || new Date().getFullYear();
    node.innerHTML = `${escapeHtml(activeSiteConfig.footerCopy || "")} · <span id="footerYear">${escapeHtml(year)}</span>`;
  });
  document.querySelectorAll(".footer-links").forEach((node) => {
    const links = Array.isArray(activeSiteConfig.footerLinks) ? activeSiteConfig.footerLinks : [];
    if (links.length) {
      node.innerHTML = links.map((link) => `<a href="${escapeHtml(link.url || "#")}">${escapeHtml(link.label || "Link")}</a>`).join("");
    }
  });
  const legalCopy = document.querySelector(".legal-hero .muted-copy");
  if (legalCopy) {
    if (window.location.pathname.endsWith("/rules.html") && activeSiteConfig.rulesCopy) legalCopy.textContent = activeSiteConfig.rulesCopy;
    if (window.location.pathname.endsWith("/privacy.html") && activeSiteConfig.privacyCopy) legalCopy.textContent = activeSiteConfig.privacyCopy;
    if (window.location.pathname.endsWith("/contact.html") && activeSiteConfig.contactCopy) legalCopy.textContent = activeSiteConfig.contactCopy;
  }
  try {
    const storedTheme = window.localStorage.getItem(SITE_THEME_STORAGE_KEY);
    if (!Auth.getCurrentUser?.()?.preferences?.siteTheme && !storedTheme) {
      applySiteTheme(activeSiteConfig.defaultTheme || "midnight", { storage: "ignore" });
    }
  } catch {
    applySiteTheme(activeSiteConfig.defaultTheme || "midnight", { storage: "ignore" });
  }
}

async function loadSiteConfig() {
  try {
    const data = await API.getSite();
    applySiteConfig(data.site || {});
  } catch {
    applySiteConfig(activeSiteConfig);
  }
}

function installAccessibilityShell() {
  const root = document.getElementById("app") || document.body;
  if (!document.querySelector(".skip-link")) {
    const link = document.createElement("a");
    link.href = "#mainContent";
    link.className = "skip-link";
    link.textContent = "Skip to main content";
    document.body.insertBefore(link, document.body.firstChild);
  }
  const main = document.querySelector("main");
  if (main) {
    main.id = main.id || "mainContent";
    main.tabIndex = -1;
  }
  const toastContainer = document.getElementById("toastContainer");
  if (toastContainer) {
    toastContainer.setAttribute("aria-live", "polite");
    toastContainer.setAttribute("aria-atomic", "true");
  }
  root?.setAttribute?.("data-js-ready", "true");
}

document.addEventListener("DOMContentLoaded", () => {
  installAccessibilityShell();
  loadSiteConfig();
  applyViewerPresentationPreferences(Auth.getCurrentUser?.() || null);
  loadEnabledPlugins();
  startLiveUpdates();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeNavMenu();
    closeModal();
    return;
  }
  if (event.key === "Tab") {
    const overlay = document.getElementById("modalOverlay");
    const modal = document.getElementById("modal");
    if (overlay && modal && !overlay.classList.contains("hidden")) {
      const focusable = Array.from(
        modal.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"),
      ).filter((node) => !node.hasAttribute("disabled"));
      if (focusable.length) {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
          return;
        }
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
          return;
        }
      }
    }
  }
  if (isTypingTarget(event.target)) return;
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    showSearchModal();
    return;
  }
  if (!event.metaKey && !event.ctrlKey && !event.altKey && event.key === "/") {
    event.preventDefault();
    showSearchModal();
  }
});

function makeAvatar(user, size = "") {
  if (!user) return "";
  const roleKey = user.role || "new";
  const role = DB.roles[roleKey] || DB.roles.new;
  const sizeClass = size ? ` avatar-${size}` : "";
  const avatarUrl = typeof user === "string" ? "" : user?.avatarUrl || user?.authorAvatarUrl || "";
  const avatarBody = avatarUrl
    ? `<img class="avatar-image" src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(`${user.username || "User"} avatar`)}" loading="lazy">`
    : initialsForUser(user);
  return `<div class="avatar${sizeClass} avatar-${escapeHtml(roleKey)}${avatarUrl ? " avatar-has-image" : ""}" style="border:2px solid ${role.color}40">${avatarBody}</div>`;
}

function roleBadge(role) {
  const resolved = DB.roles[role] || DB.roles.new;
  return `<span class="user-role-badge role-${escapeHtml(resolved.cssClass)}">${resolved.icon} ${escapeHtml(resolved.label)}</span>`;
}

const sectionManagerState = {
  categories: [],
  sections: {},
};

const dmState = {
  threads: [],
  selectedThreadId: null,
};

const navMenuState = {
  open: false,
};

const notificationState = {
  items: [],
  status: "all",
  kind: "all",
};

const reportQueueState = {
  items: [],
  status: "open",
  macros: [],
};

const appealQueueState = {
  items: [],
  status: "open",
};

const searchState = {
  timer: null,
  requestId: 0,
};

const liveState = {
  eventSource: null,
  key: "",
  reconnectTimer: null,
  reconnectDelay: 1500,
};

const pluginState = {
  styles: new Set(),
  scripts: new Set(),
};

function isTypingTarget(target) {
  const tag = target?.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable;
}

function navAttentionCount(user) {
  if (!user) return 0;
  return [
    Number(user.notificationCount || 0),
    Number(user.messageCount || 0),
        Number(user.reportCount || 0),
        Number(user.noticeCount || 0),
        Number(user.appealCount || 0),
        Number(user.registrationCount || 0),
      ].reduce((sum, count) => sum + count, 0);
}

function settingsPageHref() {
  if (typeof pageHref === "function") {
    return pageHref("settings.html");
  }
  const prefix = window.location.pathname.includes("/pages/") ? "" : "pages/";
  return `${prefix}settings.html`;
}

function currentLiveQuery() {
  if (typeof window.getLiveContext === "function") {
    const context = window.getLiveContext() || {};
    return {
      threadId: context.threadId || "",
      section: context.section || "",
    };
  }
  return {};
}

function closeLiveUpdates() {
  if (liveState.eventSource) {
    liveState.eventSource.close();
    liveState.eventSource = null;
  }
  if (liveState.reconnectTimer) {
    window.clearTimeout(liveState.reconnectTimer);
    liveState.reconnectTimer = null;
  }
}

function scheduleLiveReconnect() {
  closeLiveUpdates();
  liveState.reconnectTimer = window.setTimeout(() => {
    liveState.reconnectTimer = null;
    startLiveUpdates({ force: true });
  }, liveState.reconnectDelay);
  liveState.reconnectDelay = Math.min(liveState.reconnectDelay * 1.5, 12000);
}

function applyLiveSnapshot(snapshot = {}) {
  if (Object.prototype.hasOwnProperty.call(snapshot, "currentUser")) {
    Auth.setCurrentUser(snapshot.currentUser || null);
  } else {
    renderNavActions();
    renderSidebarUser();
  }
  if (typeof window.handleLiveSnapshot === "function") {
    window.handleLiveSnapshot(snapshot);
  }
}

function startLiveUpdates(options = {}) {
  if (!("EventSource" in window)) return;
  const query = currentLiveQuery();
  const key = JSON.stringify(query);
  if (!options.force && liveState.eventSource && liveState.key === key) {
    return;
  }
  closeLiveUpdates();
  liveState.key = key;
  liveState.reconnectDelay = 1500;
  const source = new EventSource(`/api/live/stream${buildQuery(query)}`);
  liveState.eventSource = source;
  source.addEventListener("snapshot", (event) => {
    try {
      const snapshot = JSON.parse(event.data || "{}");
      applyLiveSnapshot(snapshot);
    } catch {
      // Ignore malformed stream payloads and wait for the next frame.
    }
  });
  source.addEventListener("ping", () => {});
  source.onerror = () => {
    scheduleLiveReconnect();
  };
}

async function loadEnabledPlugins() {
  try {
    const data = await API.getPlugins();
    const plugins = data.plugins || [];
    plugins.forEach((plugin) => {
      (plugin.styles || []).forEach((href) => {
        if (pluginState.styles.has(href)) return;
        pluginState.styles.add(href);
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.dataset.pluginHref = href;
        document.head.appendChild(link);
      });
      (plugin.scripts || []).forEach((src) => {
        if (pluginState.scripts.has(src)) return;
        pluginState.scripts.add(src);
        const script = document.createElement("script");
        script.src = src;
        script.defer = true;
        script.dataset.pluginSrc = src;
        document.body.appendChild(script);
      });
    });
  } catch {
    // Plugin assets are optional; skip quietly if the endpoint is unavailable.
  }
}

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
      <button class="nav-menu-trigger" onclick="toggleNavMenu(event)" aria-expanded="${isOpen ? "true" : "false"}">
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

function renderSidebarUser() {
  const container = document.getElementById("sidebarUser");
  if (!container) return;
  const user = Auth.getCurrentUser();

  if (!user) {
    container.innerHTML = `
      <div class="sidebar-login-prompt">
        <p>Join the forum to post, like replies, and unlock member spaces.</p>
        <div class="sidebar-login-buttons">
          <button class="btn btn-primary" onclick="showLoginModal()">Log In</button>
          <button class="btn btn-ghost" onclick="showRegisterModal()">Create Account</button>
        </div>
      </div>
    `;
    return;
  }

  const xpData = DB.getXPForNextLevel(user.xp);
  const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
  container.innerHTML = `
    <div class="user-avatar-row">
      ${makeAvatar(user)}
      <div class="user-meta">
        <div class="user-name">${escapeHtml(user.username)}</div>
        ${roleBadge(user.role)}
        ${user.statusText ? `<div class="tiny-copy">${escapeHtml(user.statusText)}</div>` : ""}
      </div>
    </div>
    <div class="user-stats-grid">
      <div class="user-stat-box">
        <div class="user-stat-val">${fmtNum(user.posts || 0)}</div>
        <div class="user-stat-label">Posts</div>
      </div>
      <div class="user-stat-box">
        <div class="user-stat-val">${fmtNum(user.xp || 0)}</div>
        <div class="user-stat-label">XP</div>
      </div>
    </div>
    <div class="xp-bar-wrap">
      <div class="xp-label">
        <span>${escapeHtml(xpData.label)} Progress</span>
        <span>${progress}%</span>
      </div>
      <div class="xp-bar"><div class="xp-fill" style="width:${progress}%"></div></div>
    </div>
    <div class="stack-actions">
      <button class="btn btn-outline btn-sm" onclick="showProfile(${JSON.stringify(user.id)})">View Profile</button>
      <button class="btn btn-ghost btn-sm" onclick="goToSettingsPage()">Settings</button>
    </div>
  `;
}

function renderSidebarStats(stats) {
  const container = document.getElementById("sidebarStats");
  if (!container || !stats) return;
  container.innerHTML = `
    <li><span>Total Posts</span><strong>${fmtNum(stats.posts || 0)}</strong></li>
    <li><span>Total Threads</span><strong>${fmtNum(stats.threads || 0)}</strong></li>
    <li><span>Total Members</span><strong>${fmtNum(stats.members || 0)}</strong></li>
    <li><span>Online Now</span><strong>${fmtNum(stats.online || 0)}</strong></li>
  `;
}

function renderActivityFeed(activity = []) {
  const container = document.getElementById("activityList");
  if (!container) return;
  if (!activity.length) {
    container.innerHTML = `<li class="activity-item"><span class="activity-text">No activity yet. Start the first conversation.</span></li>`;
    return;
  }

  container.innerHTML = activity
    .map((item) => {
      const target = item.target ? ` <strong>${escapeHtml(item.target)}</strong>` : "";
      return `
        <li class="activity-item">
          <span class="activity-dot"></span>
          <span class="activity-text">
            <strong>${escapeHtml(item.user)}</strong> ${escapeHtml(item.action)}${target}
            <span class="activity-time">${escapeHtml(formatRelativeTime(item.createdAt))}</span>
          </span>
        </li>
      `;
    })
    .join("");
}

function renderTopMembers(members = []) {
  const container = document.getElementById("topMembers");
  if (!container) return;
  if (!members.length) {
    container.innerHTML = `<li class="top-member empty-top-member">No members yet.</li>`;
    return;
  }

  container.innerHTML = members
    .map((user, index) => `
      <li class="top-member" style="cursor:pointer" onclick="showProfile(${JSON.stringify(user.id)})">
        <span class="rank-num">${index + 1}</span>
        ${makeAvatar(user, "xs")}
        <div class="member-info">
          <div class="member-name">${escapeHtml(user.username)}</div>
          <div class="member-posts">${user.statusText ? escapeHtml(user.statusText) : `${fmtNum(user.posts || 0)} posts`}</div>
        </div>
        ${roleBadge(user.role)}
      </li>
    `)
    .join("");
}

function renderHeroStats(stats) {
  const posts = document.getElementById("statPosts");
  const members = document.getElementById("statMembers");
  const online = document.getElementById("statOnline");
  if (posts) posts.textContent = fmtNum(stats?.posts || 0);
  if (members) members.textContent = fmtNum(stats?.members || 0);
  if (online) online.textContent = fmtNum(stats?.online || 0);
}

function renderTicker(items = []) {
  const container = document.getElementById("tickerWrap");
  if (!container) return;
  const source = items.length ? [...items, ...items] : ["OmniForum is ready for its first real members."];
  const inner = source
    .map((item) => `<span class="ticker-item"><span class="ticker-dot"></span>${escapeHtml(item)}</span>`)
    .join("");
  container.innerHTML = `<div class="ticker-inner">${inner}</div>`;
}

function renderFooterYear() {
  const year = document.getElementById("footerYear");
  if (year) year.textContent = String(new Date().getFullYear());
}

function modalError(message) {
  return `<div class="form-error visible">${escapeHtml(message)}</div>`;
}

function showLoginModal() {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Log In</div>
    <div class="form-error" id="loginError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="loginUsername" type="text" placeholder="Your username" autocomplete="username">
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-input" id="loginPassword" type="password" placeholder="Your password" autocomplete="current-password">
    </div>
    <div class="form-group">
      <label class="form-label">Recovery Code</label>
      <input class="form-input" id="loginRecoveryCode" type="text" placeholder="Optional one-time code if you forgot your password" autocomplete="one-time-code">
      <div class="form-hint">Use this instead of a password only if you previously generated recovery codes.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doLogin()">Log In</button>
    </div>
    <div class="form-switch">Need an account? <a onclick="showRegisterModal()">Create one</a></div>
  `);

  window.setTimeout(() => document.getElementById("loginUsername")?.focus(), 50);
  document.getElementById("loginPassword")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") doLogin();
  });
}

function showRegisterModal() {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Create Account</div>
    <div class="form-error" id="regError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="regUsername" type="text" placeholder="Choose a username" maxlength="24">
      <div class="form-hint">Letters, numbers, underscores, and hyphens only.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-input" id="regPassword" type="password" placeholder="Choose a password" minlength="8">
      <div class="form-hint">Use at least 8 characters.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Confirm Password</label>
      <input class="form-input" id="regConfirm" type="password" placeholder="Confirm your password">
    </div>
    <div class="form-group">
      <label class="form-label">Invite Code</label>
      <input class="form-input" id="regInviteCode" type="text" placeholder="Optional unless the forum is invite-only" autocomplete="off">
      <div class="form-hint">If staff gave you an invite, enter it here. Some communities also require admin approval.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doRegister()">Create Account</button>
    </div>
    <div class="form-switch">Already registered? <a onclick="showLoginModal()">Log in</a></div>
  `);

  window.setTimeout(() => document.getElementById("regUsername")?.focus(), 50);
}

function showForcedPasswordResetModal() {
  const user = Auth.getCurrentUser();
  if (!user?.mustResetPassword) return;
  openModal(`
    <div class="modal-title">Reset Your Password</div>
    <div class="muted-copy">A temporary recovery password was used on this account. Set a new password to continue.</div>
    <div class="form-error" id="passwordResetError"></div>
    <div class="form-group">
      <label class="form-label">New Password</label>
      <input class="form-input" id="passwordResetNew" type="password" placeholder="Choose a new password" autocomplete="new-password">
      <div class="form-hint">Use at least 8 characters. This replaces the temporary recovery password.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Confirm Password</label>
      <input class="form-input" id="passwordResetConfirm" type="password" placeholder="Confirm the new password" autocomplete="new-password">
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="logoutUser()">Log Out</button>
      <button class="btn btn-primary" onclick="saveForcedPasswordReset()">Update Password</button>
    </div>
  `, { size: "lg", dismissible: false });

  window.setTimeout(() => document.getElementById("passwordResetNew")?.focus(), 50);
  document.getElementById("passwordResetConfirm")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveForcedPasswordReset();
  });
}

function handleAuthStateChanged(user) {
  closeNavMenu();
  applyViewerPresentationPreferences(user);
  renderNavActions();
  renderSidebarUser();
  startLiveUpdates();
  if (user?.mustResetPassword) {
    window.setTimeout(() => {
      if (Auth.mustResetPassword()) {
        showForcedPasswordResetModal();
      }
    }, 0);
    return;
  }
}

async function doLogin() {
  const error = document.getElementById("loginError");
  const username = document.getElementById("loginUsername")?.value?.trim();
  const password = document.getElementById("loginPassword")?.value || "";
  const recoveryCode = document.getElementById("loginRecoveryCode")?.value?.trim() || "";
  if (error) error.classList.remove("visible");

  try {
    const user = await Auth.login(username, password, recoveryCode);
    closeModal(null, true);
    toast(user.mustResetPassword ? `Welcome back, ${user.username}. Please set a new password.` : `Welcome back, ${user.username}.`, "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Login failed.";
      error.classList.add("visible");
    }
  }
}

async function doRegister() {
  const error = document.getElementById("regError");
  const username = document.getElementById("regUsername")?.value?.trim();
  const password = document.getElementById("regPassword")?.value || "";
  const confirm = document.getElementById("regConfirm")?.value || "";
  const inviteCode = document.getElementById("regInviteCode")?.value?.trim() || "";
  if (error) error.classList.remove("visible");

  if (password !== confirm) {
    if (error) {
      error.textContent = "Passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const data = await Auth.register(username, password, inviteCode);
    closeModal();
    if (data.pendingApproval) {
      toast(data.message || "Account created and pending admin approval.", "success", 5200);
      await refreshApp();
      return;
    }
    const user = data.currentUser;
    toast(`Welcome to OmniForum, ${user.username}.`, "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Registration failed.";
      error.classList.add("visible");
    }
  }
}

async function logoutUser() {
  try {
    await Auth.logout();
    closeModal(null, true);
    toast("Logged out.", "info");
    await refreshApp();
  } catch (err) {
    toast(err.message || "Could not log out.", "error");
  }
}

async function refreshApp() {
  renderNavActions();
  renderSidebarUser();
  if (typeof window.refreshCurrentPage === "function") {
    await window.refreshCurrentPage();
  }
}

function renderSearchThreads(threads = []) {
  if (!threads.length) {
    return `<div class="centered-message">No thread matches yet.</div>`;
  }
  return threads.map((thread) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div>
          <div class="search-result-title">${escapeHtml(thread.title)}</div>
          <div class="search-result-meta">in ${escapeHtml(thread.section.name)} · by ${escapeHtml(thread.authorName)} · ${escapeHtml(formatRelativeTime(thread.updatedAt))}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToThread(${JSON.stringify(thread.id)})">Open</button>
      </div>
      <div class="thread-badges">${renderThreadBadges(thread)} ${(thread.tags || []).length ? renderThreadTags(thread.tags) : ""}</div>
    </div>
  `).join("");
}

function renderSearchPosts(posts = []) {
  if (!posts.length) {
    return `<div class="centered-message">No post matches yet.</div>`;
  }
  return posts.map((post) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div>
          <div class="search-result-title">${escapeHtml(post.threadTitle)}</div>
          <div class="search-result-meta">post by ${escapeHtml(post.author.username)} · ${escapeHtml(post.sectionName || post.sectionId || "")} · ${escapeHtml(formatRelativeTime(post.createdAt))}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToPost(${JSON.stringify(post.threadId)}, ${JSON.stringify(post.id)})">Open Post</button>
      </div>
      <div class="search-result-copy">${escapeHtml(post.content)}</div>
    </div>
  `).join("");
}

function renderSearchMembers(members = []) {
  if (!members.length) {
    return `<div class="centered-message">No member matches yet.</div>`;
  }
  return members.map((member) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div class="search-result-user">
          ${makeAvatar(member, "xs")}
          <div>
            <div class="search-result-title">${escapeHtml(member.username)}</div>
            <div class="search-result-meta">${roleBadge(member.role)} · ${fmtNum(member.posts || 0)} posts</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(member.id)})">View</button>
      </div>
      <div class="search-result-copy">${escapeHtml(member.bio || "No bio yet.")}</div>
    </div>
  `).join("");
}

function searchFiltersFromDom() {
  return {
    q: document.getElementById("forumSearchInput")?.value?.trim() || "",
    section: document.getElementById("forumSearchSection")?.value || "",
    author: document.getElementById("forumSearchAuthor")?.value?.trim() || "",
    tag: document.getElementById("forumSearchTag")?.value?.trim() || "",
    solved: document.getElementById("forumSearchSolved")?.value || "all",
    media: document.getElementById("forumSearchMedia")?.value || "all",
    replies: document.getElementById("forumSearchReplies")?.value || "all",
    date: document.getElementById("forumSearchDate")?.value || "all",
    sort: document.getElementById("forumSearchSort")?.value || "relevance",
  };
}

function renderSearchSectionOptions(data = null) {
  const sections = data?.sections || [];
  const selected = data?.filters?.section || "";
  return [
    `<option value="">All sections</option>`,
    ...sections.map((item) => `<option value="${escapeHtml(item.id)}"${item.id === selected ? " selected" : ""}>${escapeHtml(item.name)}</option>`),
  ].join("");
}

function renderSearchModalBody(data = null, query = "") {
  const trimmed = query.trim();
  const filters = data?.filters || searchFiltersFromDom?.() || {};
  const hasActiveFilter = ["section", "author", "tag", "solved", "media", "replies", "date"]
    .some((key) => filters[key] && filters[key] !== "all");
  if (!trimmed && !hasActiveFilter) {
    return renderEmptyState("⌘", "Search the forum.", "Find threads, posts, and members from anywhere.");
  }
  if (trimmed.length > 0 && trimmed.length < 2) {
    return renderEmptyState("🔎", "Keep typing.", "Use at least 2 characters for search.");
  }
  if (!data) {
    return `<div class="centered-message">Searching…</div>`;
  }
  const total = (data.threads?.length || 0) + (data.posts?.length || 0) + (data.members?.length || 0);
  if (!total) {
    return renderEmptyState("🫥", "No matches found.", "Try a shorter term, a username, or a thread keyword.");
  }
  return `
    <div class="search-results-grid">
      <div class="search-results-group">
        <div class="page-section-title">Threads <span>${data.threads?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchThreads(data.threads || [])}</div>
      </div>
      <div class="search-results-group">
        <div class="page-section-title">Posts <span>${data.posts?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchPosts(data.posts || [])}</div>
      </div>
      <div class="search-results-group">
        <div class="page-section-title">Members <span>${data.members?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchMembers(data.members || [])}</div>
      </div>
    </div>
  `;
}

function renderSearchModal(data = null, query = "") {
  const filters = data?.filters || {};
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Search OmniForum</div>
    <div class="form-group">
      <label class="form-label">Search</label>
      <input class="form-input" id="forumSearchInput" type="text" value="${escapeHtml(query)}" placeholder="Search threads, posts, and members" autocomplete="off">
      <div class="form-hint">Tip: press <strong>/</strong> or <strong>Ctrl/Cmd+K</strong> anywhere to open search.</div>
    </div>
    <div class="form-row search-filter-grid">
      <div class="form-group">
        <label class="form-label">Section</label>
        <select class="form-input" id="forumSearchSection">${renderSearchSectionOptions(data)}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Author</label>
        <input class="form-input" id="forumSearchAuthor" type="text" value="${escapeHtml(filters.author || "")}" placeholder="username">
      </div>
      <div class="form-group">
        <label class="form-label">Tag</label>
        <input class="form-input" id="forumSearchTag" type="text" value="${escapeHtml(filters.tag || "")}" placeholder="support">
      </div>
      <div class="form-group">
        <label class="form-label">Solved</label>
        <select class="form-input" id="forumSearchSolved">
          <option value="all"${(filters.solved || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="solved"${filters.solved === "solved" ? " selected" : ""}>Solved</option>
          <option value="unsolved"${filters.solved === "unsolved" ? " selected" : ""}>Unsolved</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Media</label>
        <select class="form-input" id="forumSearchMedia">
          <option value="all"${(filters.media || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="with_media"${filters.media === "with_media" ? " selected" : ""}>Has images/GIFs</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Replies</label>
        <select class="form-input" id="forumSearchReplies">
          <option value="all"${(filters.replies || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="unanswered"${filters.replies === "unanswered" ? " selected" : ""}>Unanswered</option>
          <option value="answered"${filters.replies === "answered" ? " selected" : ""}>Answered</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Date</label>
        <select class="form-input" id="forumSearchDate">
          <option value="all"${(filters.date || "all") === "all" ? " selected" : ""}>Any time</option>
          <option value="today"${filters.date === "today" ? " selected" : ""}>Past day</option>
          <option value="week"${filters.date === "week" ? " selected" : ""}>Past week</option>
          <option value="month"${filters.date === "month" ? " selected" : ""}>Past month</option>
          <option value="year"${filters.date === "year" ? " selected" : ""}>Past year</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Sort</label>
        <select class="form-input" id="forumSearchSort">
          <option value="relevance"${(filters.sort || "relevance") === "relevance" ? " selected" : ""}>Relevance</option>
          <option value="latest"${filters.sort === "latest" ? " selected" : ""}>Latest</option>
          <option value="trending"${filters.sort === "trending" ? " selected" : ""}>Trending</option>
        </select>
      </div>
    </div>
    <div id="forumSearchResults">${renderSearchModalBody(data, query)}</div>
  `;
}

async function showSearchModal(initialQuery = "") {
  const initialText = typeof initialQuery === "string" ? initialQuery : (initialQuery?.q || "");
  openModal(renderSearchModal({
    filters: typeof initialQuery === "string" ? {} : initialQuery,
    sections: [],
  }, initialText), { size: "xl" });
  const input = document.getElementById("forumSearchInput");
  if (!input) return;
  window.setTimeout(() => {
    input.focus();
    input.select();
  }, 50);
  ["forumSearchInput", "forumSearchSection", "forumSearchAuthor", "forumSearchTag", "forumSearchSolved", "forumSearchMedia", "forumSearchReplies", "forumSearchDate", "forumSearchSort"]
    .map((id) => document.getElementById(id))
    .filter(Boolean)
    .forEach((node) => {
      node.addEventListener("input", () => scheduleGlobalSearch());
      node.addEventListener("change", () => scheduleGlobalSearch());
    });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      scheduleGlobalSearch(true);
    }
  });
  if (initialText.trim().length >= 2) {
    await scheduleGlobalSearch(true);
  }
}

async function performGlobalSearch() {
  const container = document.getElementById("forumSearchResults");
  if (!container) return;
  const filters = searchFiltersFromDom();
  const query = filters.q || "";
  const requestId = ++searchState.requestId;
  container.innerHTML = renderSearchModalBody(null, query);
  const hasActiveFilter = ["section", "author", "tag", "solved", "media", "replies", "date"]
    .some((key) => filters[key] && filters[key] !== "all");
  if (query.trim().length > 0 && query.trim().length < 2) {
    container.innerHTML = renderSearchModalBody(null, query);
    return;
  }
  if (!query.trim() && !hasActiveFilter) {
    container.innerHTML = renderSearchModalBody(null, query);
    return;
  }
  try {
    const data = await API.getSearch(filters);
    if (requestId !== searchState.requestId) return;
    const sectionSelect = document.getElementById("forumSearchSection");
    if (sectionSelect) {
      const currentValue = sectionSelect.value;
      sectionSelect.innerHTML = renderSearchSectionOptions(data);
      sectionSelect.value = currentValue || data.filters?.section || "";
    }
    container.innerHTML = renderSearchModalBody(data, query);
  } catch (err) {
    if (requestId !== searchState.requestId) return;
    container.innerHTML = renderEmptyState("⚠️", "Search failed.", err.message || "Please try again.");
  }
}

async function scheduleGlobalSearch(immediate = false) {
  if (searchState.timer) {
    window.clearTimeout(searchState.timer);
    searchState.timer = null;
  }
  if (immediate) {
    await performGlobalSearch();
    return;
  }
  searchState.timer = window.setTimeout(() => {
    performGlobalSearch();
  }, 180);
}

function notificationOpenLabel(item) {
  if (item.targetType === "dm_thread") return "Open Message";
  if (item.targetType === "user") return "Open Profile";
  if (item.targetType === "report_queue") return "Open Queue";
  if (item.targetType === "appeal_queue") return "Open Appeals";
  if (item.targetType === "contact_notice") return "Open Staff Inbox";
  if (item.targetType === "registration_queue") return "Open Signups";
  return "Open";
}

function renderNotificationCard(item) {
  const unread = !item.readAt;
  return `
    <div class="notification-card ${unread ? "unread" : ""}">
      <div class="notification-head">
        <div>
          <div class="notification-title">${escapeHtml(item.title)}</div>
          <div class="notification-meta">
            ${item.actor ? `<span>${escapeHtml(item.actor.username)}</span>` : ""}
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
          </div>
        </div>
        ${unread ? '<span class="notice-pill">New</span>' : ""}
      </div>
      ${item.body ? `<div class="notification-copy">${escapeHtml(item.body)}</div>` : ""}
      <div class="notification-actions">
        <button class="btn btn-ghost btn-sm" onclick="openNotificationTarget(${JSON.stringify(item.id)})">${notificationOpenLabel(item)}</button>
        ${unread ? `<button class="btn btn-outline btn-sm" onclick="markNotificationAsRead(${JSON.stringify(item.id)})">Mark Read</button>` : ""}
      </div>
    </div>
  `;
}

function notificationKindTabs(counts = {}, kind = "all") {
  const tabs = [
    ["all", "All", counts.unread || 0],
    ["replies", "Replies", counts.replies || 0],
    ["mentions", "Mentions", counts.mentions || 0],
    ["dms", "DMs", counts.dms || 0],
    ["likes", "Likes", counts.likes || 0],
    ["staff_actions", "Staff Actions", counts.staffActions || 0],
  ];
  if (Auth.isStaff()) tabs.push(["staff", "Staff Queues", counts.staff || 0]);
  return `
    <div class="notice-kind-tabs">
      ${tabs.map(([value, label, count]) => `
        <button class="notice-kind-tab ${kind === value ? "active" : ""}" onclick="showNotificationKind(${serializeJsArg(value)})">
          <span>${escapeHtml(label)}</span>
          ${count ? `<strong>${fmtNum(count)}</strong>` : ""}
        </button>
      `).join("")}
    </div>
  `;
}

function renderNotificationsModal(items = [], counts = { unread: 0 }, status = "all", kind = "all") {
  const body = items.length
    ? items.map((item) => renderNotificationCard(item)).join("")
    : renderEmptyState("🔔", status === "unread" ? "No unread alerts." : "No alerts yet.");
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Alerts</div>
    <div class="sort-tabs notice-filter-tabs">
      <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showNotificationStatus('all')">All</button>
      <button class="sort-tab ${status === "unread" ? "active" : ""}" onclick="showNotificationStatus('unread')">Unread (${counts.unread || 0})</button>
    </div>
    ${notificationKindTabs(counts, kind)}
    ${counts.unread ? `<div class="form-actions notification-toolbar"><button class="btn btn-ghost btn-sm" onclick="markAllNotificationsRead()">Mark All Read</button></div>` : ""}
    <div class="notification-list">${body}</div>
  `;
}

async function showNotifications(status = "all", kind = notificationState.kind || "all") {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Alerts</div>
    <div class="muted-copy">Loading notifications...</div>
  `, { size: "xl" });
  try {
    const data = await API.getNotifications({ status, kind });
    notificationState.items = data.items || [];
    notificationState.status = status;
    notificationState.kind = data.kind || kind || "all";
    renderNavActions();
    openModal(renderNotificationsModal(notificationState.items, data.counts || {}, status, notificationState.kind), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Alerts</div>
      ${modalError(err.message || "Could not load your notifications.")}
    `, { size: "lg" });
  }
}

function showNotificationStatus(status = "all") {
  return showNotifications(status, notificationState.kind || "all");
}

function showNotificationKind(kind = "all") {
  return showNotifications(notificationState.status || "all", kind);
}

async function markNotificationAsRead(notificationId) {
  try {
    await API.markNotificationRead(notificationId);
    await showNotifications(notificationState.status || "all");
  } catch (err) {
    toast(err.message || "Could not update that alert.", "error");
  }
}

async function markAllNotificationsRead() {
  const ids = notificationState.items.filter((item) => !item.readAt).map((item) => item.id);
  if (!ids.length) return;
  try {
    await API.markNotificationsRead({ ids });
    await showNotifications(notificationState.status || "all");
  } catch (err) {
    toast(err.message || "Could not mark alerts as read.", "error");
  }
}

async function openNotificationTarget(notificationId) {
  const item = notificationState.items.find((entry) => entry.id === notificationId);
  if (!item) return;
  if (!item.readAt) {
    try {
      await API.markNotificationRead(notificationId);
    } catch {
      // Best-effort mark-read; navigation should still work.
    }
  }
  renderNavActions();
  if (item.targetType === "thread") {
    closeModal(null, true);
    if (item.metadata?.postId) {
      goToPost(item.metadata.threadId || item.targetId, item.metadata.postId);
      return;
    }
    goToThread(item.targetId);
    return;
  }
  if (item.targetType === "dm_thread") {
    await showMessages(item.targetId);
    return;
  }
  if (item.targetType === "user") {
    await showProfile(item.targetId);
    return;
  }
  if (item.targetType === "report_queue") {
    if (Auth.isStaff()) {
      await showReportsQueue("open");
    }
    return;
  }
  if (item.targetType === "appeal_queue") {
    if (Auth.isStaff()) {
      await showAppealsQueue("open");
    }
    return;
  }
  if (item.targetType === "contact_notice") {
    if (Auth.isStaff()) {
      await showStaffInbox("open");
    }
    return;
  }
  if (item.targetType === "registration_queue") {
    if (Auth.isAdmin()) {
      await showSignupControls();
    }
    return;
  }
  toast("This alert does not have a direct destination yet.", "info");
}

function reportReasonOptions() {
  return [
    "Spam or Scam",
    "Harassment or Bullying",
    "Rule Violation",
    "Hate or Extremism",
    "Self-harm Concern",
    "NSFW Content",
    "Impersonation",
    "Doxxing or Privacy Risk",
    "Other",
  ].map((label) => `<option value="${escapeHtml(label)}">${escapeHtml(label)}</option>`).join("");
}

function reportPriorityOptions(selected = "normal") {
  return ["low", "normal", "high", "urgent"]
    .map((value) => `<option value="${value}"${value === selected ? " selected" : ""}>${value[0].toUpperCase()}${value.slice(1)}</option>`)
    .join("");
}

function reportCategoryOptions(selected = "") {
  const options = [
    ["", "General"],
    ["spam", "Spam"],
    ["abuse", "Abuse"],
    ["safety", "Safety"],
    ["privacy", "Privacy"],
    ["impersonation", "Impersonation"],
    ["copyright", "Copyright"],
    ["other", "Other"],
  ];
  return options
    .map(([value, label]) => `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`)
    .join("");
}

function selectedReportIds() {
  return Array.from(document.querySelectorAll(".report-select:checked"))
    .map((node) => Number(node.value))
    .filter((value) => Number.isFinite(value) && value > 0);
}

function reportMacroOptions() {
  return [
    '<option value="">Apply saved macro...</option>',
    ...((reportQueueState.macros || []).filter((macro) => macro.enabled !== false).map((macro) => (
      `<option value="${escapeHtml(String(macro.id))}">${escapeHtml(macro.title)}</option>`
    ))),
  ].join("");
}

function renderReportInternalNotes(notes = []) {
  if (!notes.length) {
    return `<div class="tiny-copy">No internal staff discussion yet.</div>`;
  }
  return `
    <div class="moderation-history-list report-note-list">
      ${notes.map((note) => `
        <div class="moderation-history-card">
          <div class="moderation-history-head">
            <div>
              <div class="moderation-history-title">${escapeHtml(note.author?.username || "Staff")}</div>
              <div class="moderation-history-meta">
                <span>${escapeHtml(formatDateTime(note.createdAt))}</span>
                <span>${escapeHtml(DB.roles[note.author?.role]?.label || "Staff")}</span>
              </div>
            </div>
          </div>
          <div class="moderation-history-copy">${escapeHtml(note.note || "")}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderReportCard(item) {
  const viewer = Auth.getCurrentUser();
  const reporterButton = item.reporter
    ? `<button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.reporter.id)})">Reporter</button>`
    : "";
  const targetButton = item.target?.type === "user"
    ? `<button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.target.id)})">View Target</button>`
    : item.target?.type === "post"
      ? `<button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToPost(${JSON.stringify(item.target.contextThreadId)}, ${JSON.stringify(item.target.id)})">View Post</button>`
      : item.target?.type === "thread"
        ? `<button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToThread(${JSON.stringify(item.target.id)})">View Thread</button>`
        : "";
  const handledMeta = item.handledBy
    ? `Reviewed by ${escapeHtml(item.handledBy.username)}${item.handledAt ? ` · ${escapeHtml(formatDateTime(item.handledAt))}` : ""}`
    : "Awaiting review";
  const slaLabel = item.slaDueAt
    ? `${item.slaState === "overdue" ? "Overdue" : "Due"} ${formatDateTime(item.slaDueAt)}`
    : "No SLA set";
  return `
    <div class="notice-card ${item.status === "resolved" ? "resolved" : ""}">
      <div class="notice-head">
        <div>
          <div class="notice-subject">${escapeHtml(item.target.label)}</div>
          <div class="notice-meta">
            <span>${escapeHtml(item.reason)}</span>
            <span>${escapeHtml(item.priority || "normal")}</span>
            ${item.category ? `<span>${escapeHtml(item.category)}</span>` : ""}
            <span>Reported by ${escapeHtml(item.reporter.username)}</span>
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
          </div>
        </div>
        <div class="stack-actions">
          <label class="checkbox-row"><input class="report-select" type="checkbox" value="${item.id}"> <span>Select</span></label>
          <span class="badge ${item.status === "resolved" ? "badge-pin" : "badge-hot"}">${item.status === "resolved" ? "Resolved" : "Open"}</span>
        </div>
      </div>
      <div class="notice-message">${escapeHtml(item.target.preview || "No preview captured.").replace(/\n/g, "<br>")}</div>
      ${item.details ? `<div class="notice-message">${escapeHtml(item.details).replace(/\n/g, "<br>")}</div>` : ""}
      <div class="detail-list notice-detail-list">
        <div><span>Review Status</span><strong>${escapeHtml(handledMeta)}</strong></div>
        <div><span>Assigned</span><strong>${escapeHtml(item.assignedTo?.username || "Unassigned")}</strong></div>
        <div><span>SLA</span><strong>${escapeHtml(slaLabel)}</strong></div>
        <div><span>Escalation</span><strong>${item.escalatedAt ? `Escalated ${escapeHtml(formatDateTime(item.escalatedAt))}` : "Not escalated"}</strong></div>
      </div>
      <div class="form-row search-filter-grid">
        <div class="form-group">
          <label class="form-label">Priority</label>
          <select class="form-input" id="reportPriority-${item.id}">${reportPriorityOptions(item.priority || "normal")}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Category</label>
          <select class="form-input" id="reportCategory-${item.id}">${reportCategoryOptions(item.category || "")}</select>
        </div>
        <div class="form-group">
          <label class="form-label">Assigned</label>
          <select class="form-input" id="reportAssigned-${item.id}">
            <option value="">Unassigned</option>
            <option value="${viewer?.id || ""}"${item.assignedTo?.id === viewer?.id ? " selected" : ""}>Assign to me</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Resolution</label>
          <input class="form-input" id="reportResolution-${item.id}" maxlength="80" value="${escapeHtml(item.resolutionCode || "")}" placeholder="warning-issued">
        </div>
        <div class="form-group">
          <label class="form-label">SLA</label>
          <select class="form-input" id="reportSla-${item.id}">
            <option value="">Keep current</option>
            <option value="0">Clear SLA</option>
            <option value="24">24 hours</option>
            <option value="72">72 hours</option>
            <option value="168">7 days</option>
          </select>
        </div>
      </div>
      <div class="form-row search-filter-grid">
        <div class="form-group">
          <label class="form-label">Macro</label>
          <select class="form-input" id="reportMacro-${item.id}" onchange="applyReportMacro(${JSON.stringify(item.id)})">${reportMacroOptions()}</select>
        </div>
        <label class="checkbox-row settings-checkbox-row">
          <input type="checkbox" id="reportEscalated-${item.id}"${item.escalatedAt ? " checked" : ""}>
          <span>Escalated for higher-priority staff follow-up</span>
        </label>
      </div>
      <div class="form-group">
        <label class="form-label">Escalation Note</label>
        <input class="form-input" id="reportEscalationNote-${item.id}" maxlength="500" value="${escapeHtml(item.escalationNote || "")}" placeholder="Why this needs escalation, assignment, or SLA attention">
      </div>
      <div class="form-group">
        <label class="form-label">Staff Note</label>
        <textarea class="form-textarea notice-note" id="reportNote-${item.id}" placeholder="Internal note for moderators/admins only.">${escapeHtml(item.adminNote || "")}</textarea>
      </div>
      <div class="page-section-title" style="margin-top:12px;">Internal Discussion</div>
      ${renderReportInternalNotes(item.internalNotes || [])}
      <div class="form-group">
        <label class="form-label">Add Internal Note</label>
        <textarea class="form-textarea notice-note" id="reportInternalNote-${item.id}" placeholder="Private staff discussion, assignment context, or escalation follow-up."></textarea>
      </div>
      <div class="notice-actions">
        ${targetButton}
        ${reporterButton}
        <button class="btn btn-outline btn-sm" onclick="addReportInternalNote(${JSON.stringify(item.id)})">Add Internal Note</button>
        <button class="btn btn-ghost btn-sm" onclick="saveReportQueueItem(${JSON.stringify(item.id)}, ${serializeJsArg(item.status)})">Save Note</button>
        <button class="btn ${item.status === "resolved" ? "btn-ghost" : "btn-primary"} btn-sm" onclick="saveReportQueueItem(${JSON.stringify(item.id)}, ${serializeJsArg(item.status === "resolved" ? "open" : "resolved")})">
          ${item.status === "resolved" ? "Reopen" : "Resolve"}
        </button>
      </div>
    </div>
  `;
}

async function showReportsQueue(status = "open") {
  if (!Auth.isStaff()) {
    toast("Only moderators and admins can open the report queue.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Reports Queue</div>
    <div class="muted-copy">Loading reports...</div>
  `, { size: "xl" });
  try {
    const data = await API.getReports(status);
    reportQueueState.items = data.items || [];
    reportQueueState.macros = data.macros || [];
    reportQueueState.status = status;
    renderNavActions();
    const body = reportQueueState.items.length
      ? reportQueueState.items.map((item) => renderReportCard(item)).join("")
      : renderEmptyState("🧹", status === "open" ? "No open reports." : "No reports in this view.");
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Reports Queue</div>
      <div class="sort-tabs notice-filter-tabs">
        <button class="sort-tab ${status === "open" ? "active" : ""}" onclick="showReportsQueue('open')">Open (${data.counts?.open || 0})</button>
        <button class="sort-tab ${status === "resolved" ? "active" : ""}" onclick="showReportsQueue('resolved')">Resolved (${data.counts?.resolved || 0})</button>
        <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showReportsQueue('all')">All</button>
      </div>
      <div class="form-actions notification-toolbar">
        <button class="btn btn-ghost btn-sm" onclick="bulkUpdateReports({ status: 'resolved' })">Resolve Selected</button>
        <button class="btn btn-ghost btn-sm" onclick="bulkUpdateReports({ status: 'open' })">Reopen Selected</button>
        <button class="btn btn-outline btn-sm" onclick="bulkUpdateReports({ priority: 'high' })">Mark High Priority</button>
        <button class="btn btn-outline btn-sm" onclick="bulkUpdateReports({ assignedTo: ${Auth.getCurrentUser()?.id || '""'} })">Assign Selected to Me</button>
      </div>
      <div class="notice-list">${body}</div>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Reports Queue</div>
      ${modalError(err.message || "Could not load the report queue.")}
    `, { size: "lg" });
  }
}

async function saveReportQueueItem(reportId, status) {
  const note = document.getElementById(`reportNote-${reportId}`)?.value || "";
  const priority = document.getElementById(`reportPriority-${reportId}`)?.value || "normal";
  const category = document.getElementById(`reportCategory-${reportId}`)?.value || "";
  const assignedTo = document.getElementById(`reportAssigned-${reportId}`)?.value || "";
  const resolutionCode = document.getElementById(`reportResolution-${reportId}`)?.value?.trim() || "";
  const slaHours = document.getElementById(`reportSla-${reportId}`)?.value || "";
  const escalated = Boolean(document.getElementById(`reportEscalated-${reportId}`)?.checked);
  const escalationNote = document.getElementById(`reportEscalationNote-${reportId}`)?.value?.trim() || "";
  try {
    const payload = { status, adminNote: note, priority, category, assignedTo, resolutionCode, escalated, escalationNote };
    if (slaHours !== "") payload.slaHours = slaHours;
    await API.updateReport(reportId, payload);
    toast(status === "resolved" ? "Report resolved." : "Report updated.", "success");
    await showReportsQueue(status === "resolved" ? "open" : reportQueueState.status || status);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    } else {
      renderNavActions();
      renderSidebarUser();
    }
  } catch (err) {
    toast(err.message || "Could not update that report.", "error");
  }
}

function applyReportMacro(reportId) {
  const select = document.getElementById(`reportMacro-${reportId}`);
  const macro = (reportQueueState.macros || []).find((item) => String(item.id) === String(select?.value || ""));
  if (!macro) return;
  const note = document.getElementById(`reportNote-${reportId}`);
  if (!note) return;
  const prefix = note.value.trim() ? `${note.value.trim()}\n\n` : "";
  note.value = `${prefix}${macro.body || ""}`.trim();
}

async function addReportInternalNote(reportId) {
  const note = document.getElementById(`reportInternalNote-${reportId}`)?.value?.trim() || "";
  if (!note) {
    toast("Write an internal note first.", "error");
    return;
  }
  try {
    await API.addReportNote(reportId, { note });
    toast("Internal note added.", "success");
    await showReportsQueue(reportQueueState.status || "open");
  } catch (err) {
    toast(err.message || "Could not add that internal note.", "error");
  }
}

async function bulkUpdateReports(payload) {
  const reportIds = selectedReportIds();
  if (!reportIds.length) {
    toast("Select one or more reports first.", "error");
    return;
  }
  try {
    await API.bulkUpdateReports({ reportIds, ...payload });
    toast("Report queue updated.", "success");
    await showReportsQueue(reportQueueState.status || "open");
  } catch (err) {
    toast(err.message || "Could not update the selected reports.", "error");
  }
}

function renderAppealCard(item) {
  return `
    <div class="notice-card ${item.status === "resolved" ? "resolved" : ""}">
      <div class="notice-head">
        <div>
          <div class="notice-subject">${escapeHtml(item.user.username)}</div>
          <div class="notice-meta">
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
            <span>${item.status === "resolved" ? "Resolved" : "Open"}</span>
          </div>
        </div>
        <span class="badge ${item.status === "resolved" ? "badge-pin" : "badge-hot"}">${item.status === "resolved" ? "Resolved" : "Open"}</span>
      </div>
      <div class="notice-message">${escapeHtml(item.message).replace(/\n/g, "<br>")}</div>
      <div class="form-group">
        <label class="form-label">Staff Note</label>
        <textarea class="form-textarea notice-note" id="appealNote-${item.id}" placeholder="Internal appeal note">${escapeHtml(item.staffNote || "")}</textarea>
      </div>
      <div class="notice-actions">
        <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.user.id)})">Open User</button>
        <button class="btn btn-ghost btn-sm" onclick="saveAppealQueueItem(${JSON.stringify(item.id)}, ${serializeJsArg(item.status)})">Save Note</button>
        <button class="btn ${item.status === "resolved" ? "btn-ghost" : "btn-primary"} btn-sm" onclick="saveAppealQueueItem(${JSON.stringify(item.id)}, ${serializeJsArg(item.status === 'resolved' ? 'open' : 'resolved')})">
          ${item.status === "resolved" ? "Reopen" : "Resolve"}
        </button>
      </div>
    </div>
  `;
}

async function showAppealsQueue(status = "open") {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  const isStaff = Auth.isStaff();
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">${isStaff ? "Appeals" : "My Appeals"}</div>
    <div class="muted-copy">Loading appeals...</div>
  `, { size: "xl" });
  try {
    const data = await API.getAppeals(status);
    appealQueueState.items = data.items || [];
    appealQueueState.status = status;
    const body = appealQueueState.items.length
      ? appealQueueState.items.map((item) => renderAppealCard(item)).join("")
      : renderEmptyState("🕊", status === "open" ? "No open appeals." : "No appeals in this view.");
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">${isStaff ? "Appeals" : "My Appeals"}</div>
      <div class="sort-tabs notice-filter-tabs">
        <button class="sort-tab ${status === "open" ? "active" : ""}" onclick="showAppealsQueue('open')">Open (${data.counts?.open || 0})</button>
        <button class="sort-tab ${status === "resolved" ? "active" : ""}" onclick="showAppealsQueue('resolved')">Resolved (${data.counts?.resolved || 0})</button>
        <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showAppealsQueue('all')">All</button>
      </div>
      ${!isStaff ? `
        <div class="form-actions notification-toolbar">
          <button class="btn btn-primary btn-sm" onclick="showAppealComposer()">Submit Appeal</button>
        </div>
      ` : ""}
      <div class="notice-list">${body}</div>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Appeals</div>
      ${modalError(err.message || "Could not load appeals.")}
    `, { size: "lg" });
  }
}

function showAppealComposer() {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Submit Appeal</div>
    <div class="muted-copy">Use this to explain why a timeout, mute, or ban should be reviewed.</div>
    <div class="form-error" id="appealCreateError"></div>
    <div class="form-group">
      <label class="form-label">Appeal</label>
      <textarea class="form-textarea" id="appealMessage" placeholder="Explain what happened, what you understand, and why staff should review this decision."></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="showAppealsQueue('all')">Back</button>
      <button class="btn btn-primary" onclick="submitAppeal()">Submit Appeal</button>
    </div>
  `, { size: "lg" });
}

async function submitAppeal() {
  const error = document.getElementById("appealCreateError");
  const message = document.getElementById("appealMessage")?.value || "";
  if (error) error.classList.remove("visible");
  try {
    await API.submitAppeal({ message });
    toast("Appeal submitted.", "success");
    await showAppealsQueue("all");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not submit that appeal.";
      error.classList.add("visible");
    }
  }
}

async function saveAppealQueueItem(appealId, status) {
  const staffNote = document.getElementById(`appealNote-${appealId}`)?.value || "";
  try {
    await API.updateAppeal(appealId, { status, staffNote });
    toast("Appeal updated.", "success");
    await showAppealsQueue(appealQueueState.status || "open");
  } catch (err) {
    toast(err.message || "Could not update that appeal.", "error");
  }
}

function opsStatusTone(status) {
  const value = String(status || "").toLowerCase();
  if (["healthy", "ok", "clear", "ready", "enabled", "success"].includes(value)) return "good";
  if (["error", "critical", "failed", "missing"].includes(value)) return "bad";
  if (["attention", "warning", "warn", "stale"].includes(value)) return "warn";
  return "neutral";
}

function renderOpsBadge(status, label) {
  return `<span class="ops-status-badge ${opsStatusTone(status)}">${escapeHtml(label || status || "Unknown")}</span>`;
}

function renderOpsKpi(label, value, hint = "", status = "neutral") {
  return `
    <div class="ops-kpi-card ${opsStatusTone(status)}">
      <div class="ops-kpi-label">${escapeHtml(label)}</div>
      <div class="ops-kpi-value">${escapeHtml(value)}</div>
      ${hint ? `<div class="ops-kpi-hint">${escapeHtml(hint)}</div>` : ""}
    </div>
  `;
}

function renderOpsDetailRows(rows = []) {
  return rows
    .filter((row) => row && row.length >= 2)
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderOpsLogEntries(entries = []) {
  if (!entries.length) {
    return '<div class="settings-empty-block">No recent errors or failed requests in the runtime log.</div>';
  }
  return entries.map((entry) => `
    <div class="ops-log-entry">
      <div class="ops-log-meta">
        ${entry.status ? `<span>HTTP ${escapeHtml(String(entry.status))}</span>` : "<span>Runtime</span>"}
        <span>${escapeHtml(formatDateTime(entry.time))}</span>
      </div>
      <code>${escapeHtml(entry.line || "")}</code>
    </div>
  `).join("");
}

function renderOpsChecklist(title, summary, checklist = {}) {
  const items = checklist.items || [];
  return `
    <div class="settings-tool-card ops-check-card">
      <div class="settings-tool-title">${escapeHtml(title)}</div>
      <div class="settings-tool-copy">${escapeHtml(summary)}</div>
      <div class="ops-check-progress">
        ${renderOpsBadge(checklist.status || "attention", `${fmtNum(checklist.complete ?? checklist.passing ?? 0)} / ${fmtNum(checklist.total || items.length)} ready`)}
      </div>
      <div class="ops-check-list">
        ${items.map((item) => `
          <div class="ops-check-item ${item.ok ? "ok" : "attention"}">
            <span>${item.ok ? "✓" : "!"}</span>
            <div>
              <strong>${escapeHtml(item.label)}</strong>
              <small>${escapeHtml(item.detail || "")}</small>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function formatAuditLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function renderAuditEvent(event) {
  const actor = event.actor || {};
  const metaEntries = Object.entries(event.metadata || {})
    .filter(([, value]) => value !== null && value !== "" && value !== undefined)
    .slice(0, 5);
  return `
    <div class="audit-event-card">
      <div class="audit-event-head">
        <div>
          <div class="audit-event-title">${escapeHtml(formatAuditLabel(event.action))}</div>
          <div class="moderation-history-meta">
            <span>${escapeHtml(formatAuditLabel(event.category))}</span>
            <span>${escapeHtml(actor.username || "System")}</span>
            <span>${escapeHtml(formatDateTime(event.createdAt))}</span>
          </div>
        </div>
        ${event.targetLabel ? `<span class="ops-status-badge neutral">${escapeHtml(event.targetLabel)}</span>` : ""}
      </div>
      ${event.reason ? `<div class="moderation-history-copy">${escapeHtml(event.reason)}</div>` : ""}
      <div class="audit-meta-grid">
        ${event.targetType ? `<div><span>Target</span><strong>${escapeHtml(formatAuditLabel(event.targetType))}${event.targetId ? ` #${escapeHtml(String(event.targetId))}` : ""}</strong></div>` : ""}
        ${actor.role ? `<div><span>Actor Role</span><strong>${escapeHtml(formatAuditLabel(actor.role))}</strong></div>` : ""}
        ${event.ipAddress ? `<div><span>IP</span><strong>${escapeHtml(event.ipAddress)}</strong></div>` : ""}
        ${metaEntries.map(([key, value]) => `<div><span>${escapeHtml(formatAuditLabel(key))}</span><strong>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : String(value))}</strong></div>`).join("")}
      </div>
    </div>
  `;
}

function renderAuditLogModal(audit) {
  const filters = audit.filters || {};
  const summary = audit.summary || {};
  const categories = audit.categories || [];
  const categoryCounts = summary.categories || {};
  const categoryOptions = ["", ...categories].map((category) => `
    <option value="${escapeHtml(category)}"${filters.category === category ? " selected" : ""}>${category ? `${formatAuditLabel(category)} (${fmtNum(categoryCounts[category] || 0)})` : "All categories"}</option>
  `).join("");
  const targetOptions = ["", "user", "thread", "post", "section", "backup", "plugin", "invite", "settings", "report", "appeal", "contact_notice", "media"].map((type) => `
    <option value="${escapeHtml(type)}"${filters.targetType === type ? " selected" : ""}>${type ? formatAuditLabel(type) : "Any target"}</option>
  `).join("");
  const limitOptions = [25, 50, 80, 120, 200].map((limit) => `
    <option value="${limit}"${Number(filters.limit || 80) === limit ? " selected" : ""}>${limit} events</option>
  `).join("");
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Audit Log</div>
    <div class="muted-copy">Searchable admin-only record of moderation, content, signup, section, plugin, and operations actions.</div>
    <div class="settings-tool-grid audit-summary-grid">
      <div class="settings-tool-card">
        <div class="settings-tool-title">${fmtNum(summary.total || 0)}</div>
        <div class="settings-tool-copy">Total audit events</div>
      </div>
      <div class="settings-tool-card">
        <div class="settings-tool-title">${escapeHtml(formatDateTime(summary.latestAt))}</div>
        <div class="settings-tool-copy">Most recent event</div>
      </div>
    </div>
    <div class="settings-form-grid audit-filter-grid">
      <div class="form-group">
        <label class="form-label">Search</label>
        <input class="form-input" id="auditSearch" value="${escapeHtml(filters.q || "")}" placeholder="Action, actor, target, reason">
      </div>
      <div class="form-group">
        <label class="form-label">Actor</label>
        <input class="form-input" id="auditActor" value="${escapeHtml(filters.actor || "")}" placeholder="Username or user ID">
      </div>
      <div class="form-group">
        <label class="form-label">Category</label>
        <select class="form-input" id="auditCategory">${categoryOptions}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Target</label>
        <select class="form-input" id="auditTargetType">${targetOptions}</select>
      </div>
      <div class="form-group">
        <label class="form-label">From</label>
        <input class="form-input" id="auditFrom" type="date" value="${escapeHtml((filters.from || "").slice(0, 10))}">
      </div>
      <div class="form-group">
        <label class="form-label">To</label>
        <input class="form-input" id="auditTo" type="date" value="${escapeHtml((filters.to || "").slice(0, 10))}">
      </div>
      <div class="form-group">
        <label class="form-label">Limit</label>
        <select class="form-input" id="auditLimit">${limitOptions}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Exact Action</label>
        <input class="form-input" id="auditAction" value="${escapeHtml(filters.action || "")}" placeholder="backup_create">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="applyAuditFilters()">Apply Filters</button>
      <button class="btn btn-outline" onclick="showAuditLog()">Reset</button>
      <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
    </div>
    <div class="audit-event-list">
      ${(audit.items || []).length ? audit.items.map(renderAuditEvent).join("") : renderEmptyState("◇", "No audit events match those filters.", "Try broadening the search or date range.")}
    </div>
  `;
}

async function showAuditLog(params = {}) {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can view the audit log.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Audit Log</div>
    <div class="muted-copy">Loading audit events...</div>
  `, { size: "xl" });
  try {
    const data = await API.getAdminAudit(params);
    openModal(renderAuditLogModal(data.audit || {}), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Audit Log</div>
      ${modalError(err.message || "Could not load the audit log.")}
      <div class="form-actions"><button class="btn btn-outline" onclick="showAdminOpsModal()">Back to Operations</button></div>
    `, { size: "lg" });
  }
}

function applyAuditFilters() {
  showAuditLog({
    q: document.getElementById("auditSearch")?.value?.trim() || "",
    actor: document.getElementById("auditActor")?.value?.trim() || "",
    category: document.getElementById("auditCategory")?.value || "",
    targetType: document.getElementById("auditTargetType")?.value || "",
    from: document.getElementById("auditFrom")?.value || "",
    to: document.getElementById("auditTo")?.value || "",
    limit: document.getElementById("auditLimit")?.value || "80",
    action: document.getElementById("auditAction")?.value?.trim() || "",
  });
}

async function showAdminOpsModal() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can open operations tools.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Operations</div>
    <div class="muted-copy">Loading health and maintenance tools...</div>
  `, { size: "xl" });
  try {
    const healthData = await API.getAdminHealth();
    const logData = await API.getAdminLogs();
    const trashData = await API.getAdminTrash(40);
    const health = healthData.health || {};
    const storage = health.storage || {};
    const runtime = health.runtime || {};
    const queues = health.queues || {};
    const analytics = health.analytics || {};
    const backups = storage.backups || [];
    const trashItems = trashData.items || [];
    const plugins = health.plugins || [];
    const pluginStatus = health.pluginStatus || {};
    const backupStatus = storage.backupStatus || {};
    const mediaUsage = storage.mediaUsage || {};
    const recovery = health.recovery || {};
    const onboarding = health.onboarding || {};
    const installChecks = health.installChecks || {};
    const logSummary = health.logs || {};
    const latestErrors = logSummary.latestErrors || [];
    const databaseFiles = storage.databaseFiles || Object.entries(storage.databases || {}).map(([name, sizeLabel]) => ({ name, sizeLabel, exists: true }));
    const mediaBuckets = mediaUsage.buckets || [];
    const queueTotal = queues.totalOpen ?? ((queues.reports || 0) + (queues.appeals || 0) + (queues.contactNotices || 0) + (queues.registrations || 0));
    const latestBackup = backupStatus.latest || backups[0] || null;
    const restoreScript = recovery.restoreScript || {};
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Operations</div>
      <div class="ops-hero">
        <div>
          <div class="ops-eyebrow">Production Health</div>
          <div class="ops-hero-title">OmniForum runtime snapshot</div>
          <div class="muted-copy">Database, media, queue, plugin, backup, and recovery readiness checks for the live instance.</div>
        </div>
        ${renderOpsBadge(recovery.status || backupStatus.status, recovery.message || backupStatus.statusLabel || "Health checked")}
      </div>
      <div class="ops-kpi-grid">
        ${renderOpsKpi("Database Size", storage.databaseTotalSize || "0B", `${fmtNum(databaseFiles.length)} files tracked`, storage.databaseMissingCount ? "warning" : "healthy")}
        ${renderOpsKpi("Media Usage", mediaUsage.totalSize || "0B", `${fmtNum(mediaUsage.totalFiles || storage.mediaAssets || 0)} files, ${fmtNum(mediaUsage.orphanedFiles || 0)} orphaned`, mediaUsage.orphanedFiles ? "warning" : "healthy")}
        ${renderOpsKpi("Backup Status", backupStatus.statusLabel || "No status", latestBackup ? `Latest: ${formatDateTime(latestBackup.createdAt)}` : "Create the first archive", backupStatus.status)}
        ${renderOpsKpi("Latest Errors", fmtNum(latestErrors.length || 0), latestErrors.length ? `Last: ${formatDateTime(latestErrors[0].time)}` : "No recent failures", latestErrors.length ? "warning" : "healthy")}
        ${renderOpsKpi("Open Queues", fmtNum(queueTotal), queueTotal ? "Staff attention needed" : "All queues clear", queues.status || (queueTotal ? "attention" : "clear"))}
        ${renderOpsKpi("Plugin Status", `${fmtNum(pluginStatus.enabled || 0)} / ${fmtNum(pluginStatus.total || plugins.length)} enabled`, pluginStatus.invalidCount ? `${fmtNum(pluginStatus.invalidCount)} invalid plugin folders` : "Manifests look good", pluginStatus.status)}
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="createAdminBackup()">Create Backup</button>
        <button class="btn btn-outline" onclick="showInstallWizard()">Setup Wizard</button>
        <button class="btn btn-outline" onclick="showAdminExportTools()">Import / Export</button>
        <button class="btn btn-outline" onclick="showStaffWorkflowTools()">Staff Workflows</button>
        <button class="btn btn-outline" onclick="runMediaCleanup()">Cleanup Orphan Media</button>
        <button class="btn btn-outline" onclick="showSignupControls()">Signup Controls</button>
        <button class="btn btn-outline" onclick="showAuditLog()">Audit Log</button>
        <button class="btn btn-outline" onclick="showPluginManager()">Manage Plugins</button>
      </div>
      <div class="settings-tool-grid ops-dashboard-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Database Storage</div>
          <div class="settings-tool-copy">Total stored SQLite data across the dedicated data folder.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Total", storage.databaseTotalSize || "0B"],
              ["Files", fmtNum(databaseFiles.length)],
              ["Missing", fmtNum(storage.databaseMissingCount || 0)],
            ])}
          </div>
          <div class="ops-mini-list">
            ${databaseFiles.map((item) => `
              <div>
                <span>${escapeHtml(item.name)}</span>
                <strong>${escapeHtml(item.exists === false ? "Missing" : item.sizeLabel || "0B")}</strong>
              </div>
            `).join("")}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Media Usage</div>
          <div class="settings-tool-copy">Upload footprint by bucket, including cleanup candidates.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Total Size", mediaUsage.totalSize || "0B"],
              ["Files", fmtNum(mediaUsage.totalFiles || 0)],
              ["Orphaned", `${fmtNum(mediaUsage.orphanedFiles || 0)} (${mediaUsage.orphanedSize || "0B"})`],
              ["Per-user Quota", `${storage.mediaQuotaBytesLabel || "0B"} / ${fmtNum(storage.mediaQuotaFiles || 0)} files`],
            ])}
          </div>
          <div class="ops-mini-list">
            ${mediaBuckets.map((bucket) => `
              <div>
                <span>${escapeHtml(bucket.label || bucket.bucket)}</span>
                <strong>${fmtNum(bucket.files || 0)} files / ${escapeHtml(bucket.sizeLabel || "0B")}</strong>
              </div>
            `).join("") || '<div><span>No media files</span><strong>0B</strong></div>'}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Backup Status</div>
          <div class="settings-tool-copy">${escapeHtml(backupStatus.check?.message || backupStatus.statusLabel || "Backup status unavailable.")}</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Archives", fmtNum(backupStatus.count || storage.backupCount || 0)],
              ["Total Size", backupStatus.totalSize || storage.backupTotalSize || "0B"],
              ["Latest", latestBackup ? formatDateTime(latestBackup.createdAt) : "Not created"],
              ["Latest Age", backupStatus.latestAgeLabel || "N/A"],
              ["Rotation", `${fmtNum(backupStatus.rotationLimit || 0)} kept`],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Recovery Readiness</div>
          <div class="settings-tool-copy">${escapeHtml(recovery.message || "Recovery readiness has not been checked yet.")}</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Backup Check", recovery.latestBackupCheck?.status ? `${recovery.latestBackupCheck.status} at ${formatDateTime(recovery.latestBackupCheck.checkedAt)}` : "Not checked"],
              ["Restore Script", restoreScript.exists ? (restoreScript.executable ? "Ready" : "Not executable") : "Missing"],
              ["Last Backup", recovery.lastBackupCreated?.time ? formatDateTime(recovery.lastBackupCreated.time) : "No backup log"],
              ["Last Restore Guide", recovery.lastRestoreGuideCheck?.time ? formatDateTime(recovery.lastRestoreGuideCheck.time) : "Not opened"],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Queue Counts</div>
          <div class="settings-tool-copy">Open staff work that may need triage.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Reports", fmtNum(queues.reports || 0)],
              ["Appeals", fmtNum(queues.appeals || 0)],
              ["Contact", fmtNum(queues.contactNotices || 0)],
              ["Registrations", fmtNum(queues.registrations || 0)],
              ["Total Open", fmtNum(queueTotal)],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Plugin Status</div>
          <div class="settings-tool-copy">Safe-loading summary for installed plugin manifests.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Installed", fmtNum(pluginStatus.total || plugins.length)],
              ["Enabled", fmtNum(pluginStatus.enabled || 0)],
              ["Disabled", fmtNum(pluginStatus.disabled || 0)],
              ["With Assets", fmtNum(pluginStatus.withClientAssets || 0)],
              ["Invalid Folders", fmtNum(pluginStatus.invalidCount || 0)],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Runtime</div>
          <div class="settings-tool-copy">Server configuration values visible to admins.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Started", formatDateTime(health.startedAt)],
              ["Uptime", `${fmtNum(health.uptimeSeconds || 0)}s`],
              ["Public URL", runtime.publicUrl || "Not set"],
              ["Request Limit", runtime.maxRequestSize || String(runtime.maxRequestBytes || 0)],
              ["Secure Cookies", runtime.secureCookies ? "Enabled" : "Disabled"],
              ["Discord Webhook", runtime.discordWebhookConfigured ? "Connected" : "Not configured"],
              ["Signup Mode", runtime.registration?.mode || "Open"],
              ["Media Processing", runtime.mediaProcessing?.enabled ? "Pillow enabled" : "Not installed"],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Latest Errors</div>
          <div class="settings-tool-copy">Recent failed requests or runtime warnings from the server log.</div>
          <div class="ops-log-list">
            ${renderOpsLogEntries(latestErrors)}
          </div>
        </div>
      </div>
      <div class="page-section-title" style="margin-top:18px;">Launch Readiness</div>
      <div class="settings-tool-grid ops-dashboard-grid">
        ${renderOpsChecklist("Admin Onboarding Checklist", "First-run setup items for site structure, policies, registration, themes, and backups.", onboarding)}
        ${renderOpsChecklist("Production Install Checker", "Hosting readiness checks for Docker, proxy files, upload folders, cookies, backup tooling, and media processing.", installChecks)}
      </div>
      <div class="page-section-title" style="margin-top:18px;">Recovery</div>
      <div class="muted-copy" style="margin-bottom:12px;">Soft-deleted threads and replies can be restored here. Restore a thread before restoring any reply inside it.</div>
      <div class="moderation-history-list">
        ${trashItems.length ? trashItems.map((item) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(item.title || (item.type === "thread" ? "Deleted thread" : "Deleted reply"))}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(item.type)}</span>
                  <span>${escapeHtml(formatDateTime(item.deletedAt))}</span>
                  ${item.section?.name ? `<span>${escapeHtml(item.section.name)}</span>` : ""}
                  ${item.threadTitle ? `<span>${escapeHtml(item.threadTitle)}</span>` : ""}
                </div>
              </div>
              <button class="btn btn-outline btn-sm" onclick="restoreTrashItem(${serializeJsArg(item.type)}, ${JSON.stringify(item.id)})">Restore</button>
            </div>
            ${item.preview ? `<div class="moderation-history-copy">${escapeHtml(item.preview)}</div>` : ""}
            <div class="tiny-copy">Deleted by ${escapeHtml(item.deletedBy?.username || "Unknown")} · ${escapeHtml(item.deleteReason || "No reason noted.")}</div>
          </div>
        `).join("") : renderEmptyState("🧺", "Trash is empty right now.")}
      </div>
      <div class="page-section-title" style="margin-top:18px;">Backup Archives</div>
      <div class="moderation-history-list">
        ${backups.length ? backups.map((item) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(item.filename)}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(item.sizeLabel || "—")}</span>
                  <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
                </div>
              </div>
              <div class="stack-actions">
                <button class="btn btn-ghost btn-sm" onclick="showBackupGuide(${serializeJsArg(item.filename)})">Restore Guide</button>
                <a class="btn btn-outline btn-sm" href="${escapeHtml(item.downloadUrl)}" target="_blank" rel="noreferrer">Download</a>
              </div>
            </div>
          </div>
        `).join("") : '<div class="centered-message settings-empty-block">No backups created yet.</div>'}
      </div>
      <div class="page-section-title" style="margin-top:18px;">Forum Analytics</div>
      <div class="settings-tool-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">7-Day Activity</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Signups", fmtNum((analytics.registrations7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Active Users", fmtNum((analytics.activeUsers7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Threads", fmtNum((analytics.threads7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Posts", fmtNum((analytics.posts7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Searches", fmtNum((analytics.searches7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Search Terms (30d)</div>
          <div class="detail-list">
            ${(analytics.topSearchTerms30d || []).length ? (analytics.topSearchTerms30d || []).map((item) => `<div><span>${escapeHtml(item.query)}</span><strong>${fmtNum(item.count)} searches</strong></div>`).join("") : "<div><span>No searches logged</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Storage Footprint</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Databases", analytics.storageFootprint?.databases || storage.databaseTotalSize || "0B"],
              ["Media", analytics.storageFootprint?.media || mediaUsage.totalSize || "0B"],
              ["Backups", backupStatus.totalSize || storage.backupTotalSize || "0B"],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Popular Tags</div>
          <div class="detail-list">
            ${(analytics.topTags || []).length ? (analytics.topTags || []).slice(0, 8).map((item) => `<div><span>#${escapeHtml(item.tag)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No tag data</span><strong>—</strong></div>"}
          </div>
        </div>
      </div>
      <div class="page-section-title" style="margin-top:18px;">Moderation Audit</div>
      <div class="settings-tool-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Active Restrictions</div>
          <div class="detail-list">
            <div><span>Banned</span><strong>${fmtNum(analytics.activeRestrictions?.banned || 0)}</strong></div>
            <div><span>Timed Out</span><strong>${fmtNum(analytics.activeRestrictions?.timedOut || 0)}</strong></div>
            <div><span>Muted</span><strong>${fmtNum(analytics.activeRestrictions?.muted || 0)}</strong></div>
            <div><span>Shadow Muted</span><strong>${fmtNum(analytics.activeRestrictions?.shadowMuted || 0)}</strong></div>
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Moderators (30d)</div>
          <div class="detail-list">
            ${(analytics.topModerators30d || []).length ? (analytics.topModerators30d || []).map((item) => `<div><span>${escapeHtml(item.username)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No staff actions</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Open Report Priorities</div>
          <div class="detail-list">
            ${(analytics.openReportPriorities || []).length ? (analytics.openReportPriorities || []).map((item) => `<div><span>${escapeHtml(item.priority)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No open reports</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Sections</div>
          <div class="detail-list">
            ${(analytics.topSections || []).length ? (analytics.topSections || []).slice(0, 5).map((item) => `<div><span>${escapeHtml(item.name)}</span><strong>${fmtNum(item.posts || 0)} posts</strong></div>`).join("") : "<div><span>No section data</span><strong>—</strong></div>"}
          </div>
        </div>
      </div>
      <div class="page-section-title" style="margin-top:18px;">Recent Logs</div>
      <pre class="forum-code-block admin-log-block"><code>${escapeHtml((logData.logs || []).join("\n") || "No logs yet.")}</code></pre>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Operations</div>
      ${modalError(err.message || "Could not load operations tools.")}
    `, { size: "lg" });
  }
}

async function createAdminBackup() {
  try {
    const data = await API.createBackup();
    if (data.downloadUrl) {
      window.open(data.downloadUrl, "_blank", "noopener");
    }
    toast(data.message || "Backup created.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not create a backup.", "error");
  }
}

async function showBackupGuide(filename) {
  try {
    const data = await API.getBackupGuide(filename);
    const guide = data.guide || {};
    const contents = guide.contents || {};
    const restore = guide.restore || {};
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Restore Guide</div>
      <div class="muted-copy">Use this checklist before restoring ${escapeHtml(guide.filename || filename)} over live data.</div>
      <div class="detail-list" style="margin-top:16px;">
        <div><span>Archive</span><strong>${escapeHtml(guide.filename || filename)}</strong></div>
        <div><span>Size</span><strong>${escapeHtml(guide.sizeLabel || "—")}</strong></div>
        <div><span>Created</span><strong>${escapeHtml(formatDateTime(guide.createdAt))}</strong></div>
        <div><span>Databases</span><strong>${fmtNum(contents.databaseCount || 0)}</strong></div>
        <div><span>Uploads</span><strong>${fmtNum(contents.mediaCount || 0)}</strong></div>
      </div>
      ${contents.missingDatabases?.length ? `<div class="form-error visible" style="margin-top:14px;">Missing DB files: ${escapeHtml(contents.missingDatabases.join(", "))}</div>` : ""}
      <div class="page-section-title" style="margin-top:18px;">Checklist</div>
      <div class="detail-list">
        ${(restore.checks || []).map((item) => `<div><span>Check</span><strong>${escapeHtml(item)}</strong></div>`).join("")}
      </div>
      <div class="page-section-title" style="margin-top:18px;">Steps</div>
      <div class="stack-list">
        ${(restore.steps || []).map((item, index) => `<div class="settings-empty-block"><strong>${index + 1}.</strong> ${escapeHtml(item)}</div>`).join("")}
      </div>
      <div class="page-section-title" style="margin-top:18px;">Restore Command</div>
      <pre class="forum-code-block admin-log-block"><code>${escapeHtml(restore.command || "No command available.")}</code></pre>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="copyTextValue(${serializeJsArg(restore.command || "")}, 'Restore command')">Copy Command</button>
        ${guide.downloadUrl ? `<a class="btn btn-primary" href="${escapeHtml(guide.downloadUrl)}" target="_blank" rel="noreferrer">Download Archive</a>` : ""}
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load that restore guide.", "error");
  }
}

async function runMediaCleanup() {
  try {
    const data = await API.cleanupMedia();
    toast(data.message || "Media cleanup complete.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not clean up media.", "error");
  }
}

function siteThemeSelectOptions(selected = "midnight") {
  return Object.entries(window.SITE_THEMES || {}).map(([id, theme]) => `
    <option value="${escapeHtml(id)}"${id === selected ? " selected" : ""}>${escapeHtml(theme.label || id)}</option>
  `).join("");
}

function footerLinkEditorRows(links = []) {
  const rows = [...links];
  while (rows.length < 4) rows.push({ label: "", url: "" });
  return rows.slice(0, 6).map((link, index) => `
    <div class="form-row search-filter-grid">
      <div class="form-group">
        <label class="form-label">Footer Label ${index + 1}</label>
        <input class="form-input site-footer-label" maxlength="40" value="${escapeHtml(link.label || "")}" placeholder="Rules">
      </div>
      <div class="form-group">
        <label class="form-label">Footer URL ${index + 1}</label>
        <input class="form-input site-footer-url" maxlength="240" value="${escapeHtml(link.url || "")}" placeholder="/pages/rules.html">
      </div>
    </div>
  `).join("");
}

function featureToggleRows(toggles = {}) {
  const labels = {
    directMessages: "Direct messages",
    uploads: "Image and GIF uploads",
    polls: "Thread polls",
    reactions: "Post reactions",
    leaderboard: "Leaderboard",
    publicMemberList: "Public member list",
    staffInbox: "Staff inbox",
  };
  return Object.entries(labels).map(([key, label]) => `
    <label class="checkbox-row settings-checkbox-row">
      <input type="checkbox" class="site-feature-toggle" data-feature="${escapeHtml(key)}"${toggles[key] !== false ? " checked" : ""}>
      <span>${escapeHtml(label)}</span>
    </label>
  `).join("");
}

function renderInstallWizard(data = {}) {
  const site = data.site || activeSiteConfig;
  const registration = data.registration || {};
  const onboarding = data.onboarding || {};
  const backupReady = (data.backups || []).length > 0;
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">First-Run Setup Wizard</div>
    <div class="muted-copy">Admin-only setup for branding, policy copy, registration mode, sections, themes, and the first backup.</div>
    <div class="settings-tool-grid" style="margin-top:16px;">
      <div class="settings-tool-card">
        <div class="settings-tool-title">Launch Progress</div>
        <div class="settings-tool-copy">${fmtNum(onboarding.complete || 0)} of ${fmtNum(onboarding.total || 0)} checklist items ready.</div>
      </div>
      <div class="settings-tool-card">
        <div class="settings-tool-title">Registration</div>
        <div class="settings-tool-copy">${escapeHtml(registration.mode || "Open")}</div>
        <button class="btn btn-outline btn-sm" onclick="showSignupControls()">Edit Signup Controls</button>
      </div>
      <div class="settings-tool-card">
        <div class="settings-tool-title">First Backup</div>
        <div class="settings-tool-copy">${backupReady ? "At least one backup archive exists." : "Create one before public launch."}</div>
        <button class="btn btn-outline btn-sm" onclick="createAdminBackup()">Create Backup</button>
      </div>
    </div>
    <div class="form-error" id="siteSettingsError"></div>
    <div class="page-section-title" style="margin-top:18px;">Branding & Homepage</div>
    <div class="settings-form-grid">
      <div class="form-group">
        <label class="form-label">Site Name</label>
        <input class="form-input" id="siteNameInput" maxlength="80" value="${escapeHtml(site.siteName || "")}">
      </div>
      <div class="form-group">
        <label class="form-label">Default Theme</label>
        <select class="form-input" id="siteDefaultTheme">${siteThemeSelectOptions(site.defaultTheme || "midnight")}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Logo Text</label>
        <input class="form-input" id="siteLogoText" maxlength="80" value="${escapeHtml(site.logoText || "")}">
      </div>
      <div class="form-group">
        <label class="form-label">Logo Mark</label>
        <input class="form-input" id="siteLogoMark" maxlength="12" value="${escapeHtml(site.logoMark || "◈")}">
      </div>
      <div class="form-group">
        <label class="form-label">Hero Eyebrow</label>
        <input class="form-input" id="siteHeroEyebrow" maxlength="80" value="${escapeHtml(site.heroEyebrow || "")}">
      </div>
      <div class="form-group">
        <label class="form-label">Hero Title</label>
        <input class="form-input" id="siteHeroTitle" maxlength="120" value="${escapeHtml(site.heroTitle || "")}">
      </div>
      <div class="form-group full">
        <label class="form-label">Hero Subtitle</label>
        <input class="form-input" id="siteHeroSubtitle" maxlength="240" value="${escapeHtml(site.heroSubtitle || "")}">
      </div>
      <div class="form-group full">
        <label class="form-label">Homepage Copy</label>
        <textarea class="form-textarea" id="siteHomepageCopy" maxlength="400">${escapeHtml(site.homepageCopy || "")}</textarea>
      </div>
    </div>
    <div class="page-section-title" style="margin-top:18px;">Policy & Support Copy</div>
    <div class="settings-form-grid">
      <div class="form-group full">
        <label class="form-label">Rules Intro</label>
        <textarea class="form-textarea" id="siteRulesCopy" maxlength="1200">${escapeHtml(site.rulesCopy || "")}</textarea>
      </div>
      <div class="form-group full">
        <label class="form-label">Privacy Intro</label>
        <textarea class="form-textarea" id="sitePrivacyCopy" maxlength="1200">${escapeHtml(site.privacyCopy || "")}</textarea>
      </div>
      <div class="form-group full">
        <label class="form-label">Contact Intro</label>
        <textarea class="form-textarea" id="siteContactCopy" maxlength="1200">${escapeHtml(site.contactCopy || "")}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Support Discord</label>
        <input class="form-input" id="siteSupportDiscord" maxlength="64" value="${escapeHtml(site.supportDiscord || "")}" placeholder="omniforum.staff">
      </div>
      <div class="form-group">
        <label class="form-label">Support URL</label>
        <input class="form-input" id="siteSupportUrl" maxlength="240" value="${escapeHtml(site.supportUrl || "")}" placeholder="/pages/contact.html">
      </div>
      <div class="form-group full">
        <label class="form-label">Upload Policy</label>
        <textarea class="form-textarea" id="siteUploadPolicy" maxlength="500">${escapeHtml(site.uploadPolicy || "")}</textarea>
      </div>
    </div>
    <div class="page-section-title" style="margin-top:18px;">SEO & Footer</div>
    <div class="settings-form-grid">
      <div class="form-group">
        <label class="form-label">SEO Title</label>
        <input class="form-input" id="siteSeoTitle" maxlength="120" value="${escapeHtml(site.seoTitle || "")}">
      </div>
      <div class="form-group">
        <label class="form-label">Footer Copy</label>
        <input class="form-input" id="siteFooterCopy" maxlength="160" value="${escapeHtml(site.footerCopy || "")}">
      </div>
      <div class="form-group full">
        <label class="form-label">SEO Description</label>
        <textarea class="form-textarea" id="siteSeoDescription" maxlength="220">${escapeHtml(site.seoDescription || "")}</textarea>
      </div>
    </div>
    ${footerLinkEditorRows(site.footerLinks || [])}
    <div class="page-section-title" style="margin-top:18px;">Feature Toggles</div>
    <div class="checkbox-stack">${featureToggleRows(site.featureToggles || {})}</div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="saveAdminSiteSettings()">Save Setup</button>
      <button class="btn btn-outline" onclick="showSectionManager()">Edit Sections</button>
      <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
    </div>
  `;
}

function collectSiteSettingsPayload() {
  const featureToggles = {};
  document.querySelectorAll(".site-feature-toggle").forEach((node) => {
    featureToggles[node.dataset.feature] = Boolean(node.checked);
  });
  const labels = Array.from(document.querySelectorAll(".site-footer-label"));
  const urls = Array.from(document.querySelectorAll(".site-footer-url"));
  const footerLinks = labels.map((labelNode, index) => ({
    label: labelNode.value.trim(),
    url: urls[index]?.value?.trim() || "",
  })).filter((link) => link.label && link.url);
  return {
    siteName: document.getElementById("siteNameInput")?.value?.trim() || "",
    logoText: document.getElementById("siteLogoText")?.value?.trim() || "",
    logoMark: document.getElementById("siteLogoMark")?.value?.trim() || "",
    heroEyebrow: document.getElementById("siteHeroEyebrow")?.value?.trim() || "",
    heroTitle: document.getElementById("siteHeroTitle")?.value?.trim() || "",
    heroSubtitle: document.getElementById("siteHeroSubtitle")?.value?.trim() || "",
    homepageCopy: document.getElementById("siteHomepageCopy")?.value || "",
    rulesCopy: document.getElementById("siteRulesCopy")?.value || "",
    privacyCopy: document.getElementById("sitePrivacyCopy")?.value || "",
    contactCopy: document.getElementById("siteContactCopy")?.value || "",
    supportDiscord: document.getElementById("siteSupportDiscord")?.value?.trim() || "",
    supportUrl: document.getElementById("siteSupportUrl")?.value?.trim() || "",
    uploadPolicy: document.getElementById("siteUploadPolicy")?.value || "",
    seoTitle: document.getElementById("siteSeoTitle")?.value?.trim() || "",
    seoDescription: document.getElementById("siteSeoDescription")?.value || "",
    footerCopy: document.getElementById("siteFooterCopy")?.value?.trim() || "",
    footerLinks,
    defaultTheme: document.getElementById("siteDefaultTheme")?.value || "midnight",
    featureToggles,
  };
}

async function showInstallWizard() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can run first-run setup.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">First-Run Setup Wizard</div>
    <div class="muted-copy">Loading site setup...</div>
  `, { size: "xl" });
  try {
    const data = await API.getAdminSiteSettings();
    openModal(renderInstallWizard(data), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">First-Run Setup Wizard</div>
      ${modalError(err.message || "Could not load site setup.")}
    `, { size: "lg" });
  }
}

async function saveAdminSiteSettings() {
  const error = document.getElementById("siteSettingsError");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.updateAdminSiteSettings(collectSiteSettingsPayload());
    applySiteConfig(data.site || {});
    toast(data.message || "Site settings saved.", "success");
    const fresh = await API.getAdminSiteSettings();
    openModal(renderInstallWizard(fresh), { size: "xl" });
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save site settings.";
      error.classList.add("visible");
    } else {
      toast(err.message || "Could not save site settings.", "error");
    }
  }
}

function renderAdminExportTools() {
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Import / Export Tools</div>
    <div class="muted-copy">Admin-readable exports for backups, audits, migrations, and safer restore planning. Import preview never writes live data.</div>
    <div class="settings-form-grid" style="margin-top:16px;">
      <div class="form-group">
        <label class="form-label">Export Type</label>
        <select class="form-input" id="adminExportType">
          <option value="all">All Data JSON</option>
          <option value="users">Users</option>
          <option value="threads">Threads</option>
          <option value="posts">Posts</option>
          <option value="reports">Reports</option>
          <option value="moderation">Moderation Logs</option>
          <option value="settings">Settings</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Format</label>
        <select class="form-input" id="adminExportFormat">
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
        </select>
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="runAdminExport()">Download Export</button>
      <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
    </div>
    <div class="page-section-title" style="margin-top:18px;">Import Preview</div>
    <div class="form-error" id="adminImportPreviewError"></div>
    <textarea class="form-textarea" id="adminImportContent" placeholder="Paste an OmniForum JSON export here to preview counts before planning a restore."></textarea>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="previewAdminImport()">Preview JSON</button>
    </div>
    <div id="adminImportPreviewResult"></div>
  `;
}

async function showAdminExportTools() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can export site data.", "error");
    return;
  }
  openModal(renderAdminExportTools(), { size: "lg" });
}

async function runAdminExport() {
  try {
    const data = await API.getAdminExport({
      type: document.getElementById("adminExportType")?.value || "all",
      format: document.getElementById("adminExportFormat")?.value || "json",
    });
    const exportData = data.export || {};
    downloadTextFile(exportData.filename, exportData.content || "", exportData.contentType || "text/plain");
    toast("Admin export downloaded.", "success");
  } catch (err) {
    toast(err.message || "Could not create that export.", "error");
  }
}

async function previewAdminImport() {
  const error = document.getElementById("adminImportPreviewError");
  const result = document.getElementById("adminImportPreviewResult");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.previewAdminImport({
      content: document.getElementById("adminImportContent")?.value || "",
    });
    const preview = data.preview || {};
    if (result) {
      result.innerHTML = `
        <div class="settings-tool-card" style="margin-top:14px;">
          <div class="settings-tool-title">Preview Ready</div>
          <div class="settings-tool-copy">${escapeHtml(data.message || "No data was changed.")}</div>
          <div class="detail-list">
            ${Object.entries(preview.counts || {}).map(([key, value]) => `<div><span>${escapeHtml(key)}</span><strong>${fmtNum(value)}</strong></div>`).join("") || "<div><span>Items</span><strong>0</strong></div>"}
          </div>
          <div class="tiny-copy">${(preview.warnings || []).map(escapeHtml).join(" · ")}</div>
        </div>
      `;
    }
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not preview that import.";
      error.classList.add("visible");
    }
  }
}

async function showStaffWorkflowTools() {
  if (!Auth.isStaff()) {
    toast("Only moderators and admins can manage workflow tools.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Staff Workflow Tools</div>
    <div class="muted-copy">Loading saved moderation macros...</div>
  `, { size: "lg" });
  try {
    const data = await API.getReportMacros();
    const macros = data.macros || [];
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Staff Workflow Tools</div>
      <div class="muted-copy">Saved macros are available inside the report queue for consistent triage notes, escalations, and resolution language.</div>
      <div class="form-error" id="macroEditorError"></div>
      <div class="settings-form-grid" style="margin-top:16px;">
        <div class="form-group">
          <label class="form-label">Macro Title</label>
          <input class="form-input" id="macroTitle" maxlength="80" placeholder="Asked for more context">
        </div>
        <div class="form-group">
          <label class="form-label">Category</label>
          <input class="form-input" id="macroCategory" maxlength="40" placeholder="triage">
        </div>
        <div class="form-group full">
          <label class="form-label">Macro Body</label>
          <textarea class="form-textarea" id="macroBody" maxlength="1200" placeholder="Internal note text staff can apply to a report."></textarea>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="createStaffMacro()">Save Macro</button>
        <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
      </div>
      <div class="moderation-history-list" style="margin-top:16px;">
        ${macros.length ? macros.map((macro) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(macro.title)}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(macro.category || "general")}</span>
                  <span>${macro.enabled ? "Enabled" : "Disabled"}</span>
                </div>
              </div>
              <button class="btn btn-outline btn-sm" onclick="toggleStaffMacro(${JSON.stringify(macro.id)}, ${macro.enabled ? "false" : "true"})">${macro.enabled ? "Disable" : "Enable"}</button>
            </div>
            <div class="moderation-history-copy">${escapeHtml(macro.body)}</div>
          </div>
        `).join("") : renderEmptyState("◇", "No saved macros yet.")}
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load workflow tools.", "error");
  }
}

async function createStaffMacro() {
  const error = document.getElementById("macroEditorError");
  if (error) error.classList.remove("visible");
  try {
    await API.createReportMacro({
      title: document.getElementById("macroTitle")?.value?.trim() || "",
      category: document.getElementById("macroCategory")?.value?.trim() || "",
      body: document.getElementById("macroBody")?.value || "",
      enabled: true,
    });
    toast("Macro saved.", "success");
    await showStaffWorkflowTools();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save that macro.";
      error.classList.add("visible");
    }
  }
}

async function toggleStaffMacro(macroId, enabled) {
  try {
    await API.updateReportMacro(macroId, { enabled });
    toast("Macro updated.", "success");
    await showStaffWorkflowTools();
  } catch (err) {
    toast(err.message || "Could not update that macro.", "error");
  }
}

function renderSignupControls(controls = {}) {
  const settings = controls.settings || {};
  const pending = controls.pending || [];
  const invites = controls.invites || [];
  const pendingBody = pending.length
    ? pending.map((item) => `
      <div class="moderation-history-card">
        <div class="moderation-history-head">
          <div>
            <div class="moderation-history-title">${escapeHtml(item.username)}</div>
            <div class="moderation-history-meta">
              <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
              ${item.inviteCodeUsed ? `<span>Invite: ${escapeHtml(item.inviteCodeUsed)}</span>` : "<span>No invite</span>"}
              ${item.registrationIp ? `<span>IP: ${escapeHtml(item.registrationIp)}</span>` : ""}
            </div>
          </div>
          ${roleBadge(item.role || "new")}
        </div>
        <textarea class="form-textarea notice-note" id="registrationNote-${item.id}" maxlength="500" placeholder="Optional internal review note"></textarea>
        <div class="form-actions">
          <button class="btn btn-primary btn-sm" onclick="reviewSignup(${JSON.stringify(item.id)}, 'approve')">Approve</button>
          <button class="btn btn-danger btn-sm" onclick="reviewSignup(${JSON.stringify(item.id)}, 'reject')">Reject</button>
        </div>
      </div>
    `).join("")
    : renderEmptyState("✓", "No registrations are waiting for approval.");
  const inviteBody = invites.length
    ? invites.map((invite) => `
      <div class="moderation-history-card">
        <div class="moderation-history-head">
          <div>
            <div class="moderation-history-title">${escapeHtml(invite.code)}</div>
            <div class="moderation-history-meta">
              <span>${invite.enabled ? "Enabled" : "Disabled"}</span>
              <span>${fmtNum(invite.uses || 0)} / ${fmtNum(invite.maxUses || 0)} used</span>
              ${invite.expiresAt ? `<span>${invite.expired ? "Expired" : "Expires"} ${escapeHtml(formatDateTime(invite.expiresAt))}</span>` : "<span>No expiry</span>"}
            </div>
          </div>
          <div class="stack-actions">
            <button class="btn btn-ghost btn-sm" onclick="copyTextValue(${serializeJsArg(invite.code)}, 'Invite code')">Copy</button>
            <button class="btn ${invite.enabled ? "btn-outline" : "btn-primary"} btn-sm" onclick="toggleInvite(${JSON.stringify(invite.id)}, ${invite.enabled ? "false" : "true"})">${invite.enabled ? "Disable" : "Enable"}</button>
          </div>
        </div>
        ${invite.note ? `<div class="moderation-history-copy">${escapeHtml(invite.note)}</div>` : ""}
        <div class="tiny-copy">Remaining uses: ${fmtNum(invite.remainingUses || 0)}${invite.createdBy?.username ? ` · Created by ${escapeHtml(invite.createdBy.username)}` : ""}</div>
      </div>
    `).join("")
    : renderEmptyState("◇", "No invite codes yet.", "Create one when you want invite-only registration.");

  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Signup Controls</div>
    <div class="muted-copy">Admin-only registration controls for invite-only mode, approval review, throttling, and blocked username patterns.</div>
    <div class="settings-tool-grid" style="margin-top:16px;">
      <div class="settings-tool-card">
        <div class="settings-tool-title">Mode</div>
        <div class="detail-list">
          <div><span>Current</span><strong>${escapeHtml(settings.mode || "Open")}</strong></div>
          <div><span>Pending</span><strong>${fmtNum(controls.pendingCount || 0)}</strong></div>
        </div>
      </div>
      <div class="settings-tool-card">
        <div class="settings-tool-title">Abuse Controls</div>
        <div class="detail-list">
          <div><span>Invite Gate</span><strong>${settings.inviteRequired ? "On" : "Off"}</strong></div>
          <div><span>Approval Queue</span><strong>${settings.approvalRequired ? "On" : "Off"}</strong></div>
          <div><span>Captcha</span><strong>${settings.captchaSupported ? "Enabled" : "Not configured"}</strong></div>
        </div>
      </div>
    </div>
    <div class="form-error" id="signupControlsError"></div>
    <div class="page-section-title" style="margin-top:18px;">Registration Settings</div>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupPublic"${settings.publicRegistrationEnabled ? " checked" : ""}> <span>Allow public registration without closing the signup form entirely</span></label>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupInviteRequired"${settings.inviteRequired ? " checked" : ""}> <span>Require a valid invite code</span></label>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupApprovalRequired"${settings.approvalRequired ? " checked" : ""}> <span>Require admin approval before new users can log in</span></label>
    <div class="form-group" style="margin-top:14px;">
      <label class="form-label">Blocked Username Patterns</label>
      <textarea class="form-textarea" id="signupBlockedPatterns" maxlength="4000" placeholder="admin*\n*support*\nmoderator">${escapeHtml(settings.blockedUsernamePatterns || "")}</textarea>
      <div class="form-hint">One pattern per line. Use wildcards like <code>admin*</code>, or plain words to block usernames containing that word.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="saveSignupSettings()">Save Signup Settings</button>
      <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
    </div>
    <div class="page-section-title" style="margin-top:18px;">Create Invite</div>
    <div class="settings-form-grid">
      <div class="form-group">
        <label class="form-label">Custom Code</label>
        <input class="form-input" id="inviteCode" maxlength="40" placeholder="Leave blank to generate">
      </div>
      <div class="form-group">
        <label class="form-label">Max Uses</label>
        <input class="form-input" id="inviteMaxUses" type="number" min="1" max="500" value="1">
      </div>
      <div class="form-group">
        <label class="form-label">Expires In Days</label>
        <input class="form-input" id="inviteExpiresInDays" type="number" min="1" max="365" placeholder="Optional">
      </div>
      <div class="form-group full">
        <label class="form-label">Staff Note</label>
        <input class="form-input" id="inviteNote" maxlength="160" placeholder="Who this invite is for">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="createSignupInvite()">Create Invite Code</button>
    </div>
    <div class="page-section-title" style="margin-top:18px;">Approval Queue</div>
    <div class="moderation-history-list">${pendingBody}</div>
    <div class="page-section-title" style="margin-top:18px;">Invite Codes</div>
    <div class="moderation-history-list">${inviteBody}</div>
    <div class="tiny-copy" style="margin-top:14px;">${escapeHtml(settings.captchaNote || "")}</div>
  `;
}

async function showSignupControls() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can manage signup controls.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Signup Controls</div>
    <div class="muted-copy">Loading registration controls...</div>
  `, { size: "xl" });
  try {
    const data = await API.getAdminRegistration();
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Signup Controls</div>
      ${modalError(err.message || "Could not load signup controls.")}
    `, { size: "lg" });
  }
}

async function saveSignupSettings() {
  const error = document.getElementById("signupControlsError");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.updateRegistrationSettings({
      publicRegistrationEnabled: Boolean(document.getElementById("signupPublic")?.checked),
      inviteRequired: Boolean(document.getElementById("signupInviteRequired")?.checked),
      approvalRequired: Boolean(document.getElementById("signupApprovalRequired")?.checked),
      blockedUsernamePatterns: document.getElementById("signupBlockedPatterns")?.value || "",
    });
    toast(data.message || "Signup settings saved.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save signup settings.";
      error.classList.add("visible");
    } else {
      toast(err.message || "Could not save signup settings.", "error");
    }
  }
}

async function createSignupInvite() {
  try {
    const data = await API.createInvite({
      code: document.getElementById("inviteCode")?.value?.trim() || "",
      maxUses: Number(document.getElementById("inviteMaxUses")?.value || 1),
      expiresInDays: document.getElementById("inviteExpiresInDays")?.value || "",
      note: document.getElementById("inviteNote")?.value?.trim() || "",
    });
    toast(data.message || "Invite created.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not create invite.", "error");
  }
}

async function toggleInvite(inviteId, enabled) {
  try {
    const data = await API.updateInvite(inviteId, { enabled });
    toast(data.message || "Invite updated.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not update invite.", "error");
  }
}

async function reviewSignup(userId, action) {
  const note = document.getElementById(`registrationNote-${userId}`)?.value || "";
  try {
    const data = await API.reviewRegistration(userId, { action, note });
    toast(data.message || "Registration reviewed.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not review that registration.", "error");
  }
}

async function showPluginManager() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can manage plugins.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Plugin Manager</div>
    <div class="muted-copy">Loading installed plugins...</div>
  `, { size: "lg" });
  try {
    const data = await API.getPlugins({ includeAll: 1 });
    const plugins = data.plugins || [];
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Plugin Manager</div>
      <div class="muted-copy">Only enabled plugins with manifest-declared client assets can load into OmniForum. CSS/JS changes may need a refresh to fully unload.</div>
      <div class="moderation-history-list" style="margin-top:18px;">
        ${plugins.length ? plugins.map((plugin) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(plugin.name)}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(plugin.id)}</span>
                  <span>v${escapeHtml(plugin.version || "0.0.0")}</span>
                  <span>${plugin.enabled ? "Enabled" : "Disabled"}</span>
                </div>
              </div>
              <button class="btn ${plugin.enabled ? "btn-outline" : "btn-primary"} btn-sm" onclick="togglePluginState(${serializeJsArg(plugin.id)}, ${plugin.enabled ? "false" : "true"})">
                ${plugin.enabled ? "Disable" : "Enable"}
              </button>
            </div>
            ${plugin.description ? `<div class="moderation-history-copy">${escapeHtml(plugin.description)}</div>` : ""}
            <div class="detail-list" style="margin-top:10px;">
              <div><span>Directory</span><strong>${escapeHtml(plugin.directory)}</strong></div>
              <div><span>Assets</span><strong>${fmtNum(plugin.assetCounts?.styles || 0)} CSS · ${fmtNum(plugin.assetCounts?.scripts || 0)} JS · ${fmtNum(plugin.assetCounts?.assets || 0)} files</strong></div>
              <div><span>Loading Rules</span><strong>Enabled + manifest-declared only</strong></div>
            </div>
          </div>
        `).join("") : renderEmptyState("🧩", "No plugins are installed yet.", "Create plugin folders under /plugins with a plugin.json manifest.")}
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load the plugin manager.", "error");
  }
}

async function togglePluginState(pluginId, enabled) {
  try {
    const data = await API.updatePlugin(pluginId, { enabled });
    if (enabled) {
      await loadEnabledPlugins();
    }
    toast(data.message || "Plugin updated.", "success");
    await showPluginManager();
  } catch (err) {
    toast(err.message || "Could not update that plugin.", "error");
  }
}

async function restoreTrashItem(type, id) {
  try {
    const data = await API.restoreAdminTrash({ type, id });
    toast(data.message || "Item restored.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not restore that item.", "error");
  }
}

function showReportModal(targetType, targetId, label = "") {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Report ${escapeHtml(label || targetType)}</div>
    <div class="muted-copy">Reports go to moderators and admins for review.</div>
    <div class="form-error" id="reportCreateError"></div>
    <div class="form-group">
      <label class="form-label">Reason</label>
      <select class="form-input" id="reportReason">${reportReasonOptions()}</select>
    </div>
    <div class="form-group">
      <label class="form-label">Details</label>
      <textarea class="form-textarea" id="reportDetails" placeholder="Add any context that will help staff review this."></textarea>
      <div class="form-hint">Include what happened and why you think staff should review it.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-danger" onclick="submitReport(${serializeJsArg(targetType)}, ${JSON.stringify(targetId)})">Submit Report</button>
    </div>
  `, { size: "lg" });
}

async function submitReport(targetType, targetId) {
  const error = document.getElementById("reportCreateError");
  const reason = document.getElementById("reportReason")?.value || "";
  const details = document.getElementById("reportDetails")?.value || "";
  if (error) error.classList.remove("visible");
  try {
    const data = await API.submitReport({ targetType, targetId, reason, details });
    closeModal(null, true);
    renderNavActions();
    toast(data.message || "Report submitted.", "success");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not submit that report.";
      error.classList.add("visible");
    }
  }
}

function renderMessageThreadList(threads = [], selectedThreadId = null) {
  if (!threads.length) {
    return `
      <div class="centered-message dm-thread-empty">
        No conversations yet.
        <div class="empty-subtext">Open a member profile and use Message to start a private chat.</div>
      </div>
    `;
  }

  return threads.map((thread) => {
    const unreadCount = Number(thread.unreadCount || 0);
    const preview = thread.lastMessage?.content || "No messages yet.";
    const time = thread.lastMessage?.createdAt ? formatRelativeTime(thread.lastMessage.createdAt) : "";
    return `
      <button class="dm-thread-row ${selectedThreadId === thread.id ? "active" : ""}" onclick="showMessages(${JSON.stringify(thread.id)})">
        <div class="dm-thread-avatar">${makeAvatar(thread.otherUser, "xs")}</div>
        <div class="dm-thread-main">
          <div class="dm-thread-top">
            <span class="dm-thread-name">${escapeHtml(thread.otherUser.username)}</span>
            ${unreadCount ? `<span class="notice-pill">${unreadCount}</span>` : ""}
          </div>
          <div class="dm-thread-preview">${thread.lastMessage?.fromViewer ? "You: " : ""}${escapeHtml(preview)}</div>
        </div>
        <div class="dm-thread-time">${escapeHtml(time)}</div>
      </button>
    `;
  }).join("");
}

function renderMessageBubbles(messages = []) {
  if (!messages.length) {
    return renderEmptyState("✉️", "No messages yet.", "Send the first message to start this conversation.");
  }

  return messages.map((message) => `
    <div class="dm-message ${message.isMine ? "mine" : "theirs"}">
      <div class="dm-message-meta">
        <button class="dm-message-author" onclick="showProfile(${JSON.stringify(message.sender.id)})">${escapeHtml(message.sender.username)}</button>
        <span>${escapeHtml(formatDateTime(message.createdAt))}${message.isMine && message.readAt ? " · Read" : ""}</span>
      </div>
      <div class="dm-bubble">${escapeHtml(message.content).replace(/\n/g, "<br>")}</div>
    </div>
  `).join("");
}

function renderMessagePanel(thread, messages = []) {
  if (!thread) {
    return `
      <div class="dm-panel dm-panel-empty">
        ${renderEmptyState("💬", "Select a conversation.", "Open any thread on the left, or visit a member profile to start one.")}
      </div>
    `;
  }

  return `
    <div class="dm-panel">
      <div class="dm-panel-header">
        <div class="dm-panel-user">
          ${makeAvatar(thread.otherUser)}
          <div>
            <div class="dm-panel-name">${escapeHtml(thread.otherUser.username)}</div>
            <div class="dm-panel-meta">${roleBadge(thread.otherUser.role)}${thread.otherUser.online ? ' <span class="online-dot"></span>' : ""}</div>
          </div>
        </div>
        <div class="stack-actions">
          <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(thread.otherUser.id)})">View Profile</button>
        </div>
      </div>
      <div class="dm-message-list">${renderMessageBubbles(messages)}</div>
      <div class="form-error" id="dmReplyError"></div>
      <div class="form-group">
        <label class="form-label">Reply</label>
        <textarea class="form-textarea dm-reply-textarea" id="dmReplyBody" placeholder="Write a private message to ${escapeHtml(thread.otherUser.username)}"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="replyToDirectMessage(${JSON.stringify(thread.id)})">Send Reply</button>
      </div>
    </div>
  `;
}

function renderMessagesModal(thread, messages = []) {
  const selectedThreadId = thread?.id || null;
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Direct Messages</div>
    <div class="dm-layout">
      <aside class="dm-sidebar">
        <div class="dm-sidebar-copy">Private 1:1 conversations across the forum.</div>
        <div class="dm-thread-list">${renderMessageThreadList(dmState.threads, selectedThreadId)}</div>
      </aside>
      ${renderMessagePanel(thread, messages)}
    </div>
  `;
}

async function showMessages(selectedThreadId = null) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Direct Messages</div>
    <div class="muted-copy">Loading conversations...</div>
  `, { size: "xl" });

  try {
    const data = await API.getMessages();
    dmState.threads = data.threads || [];
    let thread = null;
    let messages = [];
    const fallbackThreadId = selectedThreadId || dmState.threads[0]?.id || null;
    if (fallbackThreadId) {
      const threadData = await API.getMessageThread(fallbackThreadId);
      thread = threadData.thread || null;
      messages = threadData.messages || [];
      dmState.selectedThreadId = thread?.id || null;
      if (thread) {
        dmState.threads = dmState.threads.map((item) => (item.id === thread.id ? { ...item, ...thread } : item));
      }
    } else {
      dmState.selectedThreadId = null;
    }
    openModal(renderMessagesModal(thread, messages), { size: "xl" });
    renderNavActions();
    const reply = document.getElementById("dmReplyBody");
    if (reply) {
      window.setTimeout(() => reply.focus(), 50);
      reply.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && dmState.selectedThreadId) {
          replyToDirectMessage(dmState.selectedThreadId);
        }
      });
    }
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Direct Messages</div>
      ${modalError(err.message || "Could not load your conversations.")}
    `, { size: "lg" });
  }
}

function showComposeMessageModal(userId, username) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  if (Auth.getCurrentUser()?.id === userId) {
    toast("You cannot message yourself.", "error");
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Message ${escapeHtml(username)}</div>
    <div class="muted-copy">This starts a private direct-message thread between the two of you.</div>
    <div class="form-error" id="dmComposeError"></div>
    <div class="form-group">
      <label class="form-label">Message</label>
      <textarea class="form-textarea dm-reply-textarea" id="dmComposeBody" placeholder="Write your message to ${escapeHtml(username)}"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="sendDirectMessage(${JSON.stringify(userId)})">Send Message</button>
    </div>
  `, { size: "lg" });

  window.setTimeout(() => document.getElementById("dmComposeBody")?.focus(), 50);
}

async function sendDirectMessage(userId) {
  const error = document.getElementById("dmComposeError");
  const content = document.getElementById("dmComposeBody")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.sendMessage({ recipientUserId: userId, content });
    renderNavActions();
    await showMessages(data.thread?.id || null);
    toast(data.message || "Direct message sent.", "success");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not send that message.";
      error.classList.add("visible");
    }
  }
}

async function replyToDirectMessage(threadId) {
  const error = document.getElementById("dmReplyError");
  const content = document.getElementById("dmReplyBody")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.replyToMessage(threadId, { content });
    renderNavActions();
    await showMessages(data.thread?.id || threadId);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not send that reply.";
      error.classList.add("visible");
    }
  }
}

function normalizeSectionManagerCategories(categories = []) {
  return categories.map((category) => ({
    ...category,
    sections: (category.sections || []).map((section) => ({
      ...section,
      categoryId: section.categoryId || category.id,
      categoryLabel: section.categoryLabel || category.label,
    })),
  }));
}

function indexManagedSections(categories = []) {
  sectionManagerState.sections = {};
  categories.forEach((category) => {
    (category.sections || []).forEach((section) => {
      sectionManagerState.sections[section.id] = section;
    });
  });
}

function roleOptionsHtml(selectedRole) {
  return Object.values(DB.roles)
    .sort((left, right) => left.level - right.level)
    .map((role) => `<option value="${escapeHtml(role.cssClass)}"${role.cssClass === selectedRole ? " selected" : ""}>${escapeHtml(role.label)}</option>`)
    .join("");
}

function categoryOptionsHtml(selectedCategoryId = "") {
  return sectionManagerState.categories
    .map((category) => `<option value="${escapeHtml(category.id)}"${category.id === selectedCategoryId ? " selected" : ""}>${escapeHtml(category.label)}</option>`)
    .join("");
}

function renderSectionManagerCard(section) {
  const openButton = section.canView
    ? `<button class="btn btn-ghost btn-sm" onclick="openManagedSection(${serializeJsArg(section.id)})">Open</button>`
    : "";
  return `
    <div class="section-admin-card">
      <div class="section-admin-head">
        <div>
          <div class="section-admin-title">${escapeHtml(section.name)}</div>
          <div class="section-admin-meta">
            <span>${escapeHtml(section.id)}</span>
            <span>Read: ${escapeHtml(DB.roles[section.requiredRole]?.label || section.requiredRole)}</span>
            <span>Post: ${escapeHtml(DB.roles[section.writeRole]?.label || section.writeRole)}</span>
            <span>${fmtNum(section.threads || 0)} threads</span>
          </div>
        </div>
        <div class="stack-actions">
          ${openButton}
          <button class="btn btn-outline btn-sm" onclick="showSectionEditor(${serializeJsArg(section.id)})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="confirmDeleteSection(${serializeJsArg(section.id)})">Delete</button>
        </div>
      </div>
      <div class="muted-copy">${escapeHtml(section.desc)}</div>
    </div>
  `;
}

function renderSectionManagerOverview() {
  const groups = sectionManagerState.categories
    .map((category) => {
      const sections = (category.sections || []).length
        ? category.sections.map((section) => renderSectionManagerCard(section)).join("")
        : `<div class="centered-message">No sections in this category yet.</div>`;
      return `
        <div class="section-admin-group">
          <div class="page-section-title">${escapeHtml(category.label)}</div>
          <div class="section-admin-list">${sections}</div>
        </div>
      `;
    })
    .join("");
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Section Manager</div>
    <div class="muted-copy">Admins and the owner can create, edit, move, reorder, and remove forum sections here.</div>
    <div class="form-actions section-admin-toolbar">
      <button class="btn btn-primary" onclick="showSectionEditor()">+ New Section</button>
    </div>
    <div class="section-admin-groups">${groups}</div>
  `;
}

async function showSectionManager(focusSectionId = "") {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can manage sections.", "error");
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Section Manager</div>
    <div class="muted-copy">Loading section controls...</div>
  `, { size: "xl" });

  try {
    const data = await API.getHome();
    sectionManagerState.categories = normalizeSectionManagerCategories(data.categories || []);
    indexManagedSections(sectionManagerState.categories);
    if (focusSectionId) {
      await showSectionEditor(focusSectionId);
      return;
    }
    openModal(renderSectionManagerOverview(), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Section Manager</div>
      ${modalError(err.message || "Could not load the section manager.")}
    `, { size: "lg" });
  }
}

async function showSectionEditor(sectionId = "") {
  if (!sectionManagerState.categories.length) {
    await showSectionManager(sectionId);
    return;
  }

  const section = sectionId ? sectionManagerState.sections[sectionId] : null;
  const title = section ? "Edit Section" : "Create Section";
  const deleteButton = section
    ? `<button class="btn btn-danger" onclick="confirmDeleteSection(${serializeJsArg(section.id)})">Delete Section</button>`
    : "";
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">${title}</div>
    <div class="form-error" id="sectionEditorError"></div>
    <div class="form-group">
      <label class="form-label">Section Name</label>
      <input class="form-input" id="sectionEditorName" maxlength="60" value="${escapeHtml(section?.name || "")}" placeholder="General Discussion">
    </div>
    <div class="form-group">
      <label class="form-label">Section Slug</label>
      <input class="form-input" id="sectionEditorSlug" maxlength="48" value="${escapeHtml(section?.id || "")}" placeholder="general-discussion">
      <div class="form-hint">Letters, numbers, hyphens, and underscores only. Leave close to the name.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Category</label>
      <select class="form-input" id="sectionEditorCategory">${categoryOptionsHtml(section?.categoryId || sectionManagerState.categories[0]?.id || "")}</select>
    </div>
    <div class="form-group">
      <label class="form-label">Description</label>
      <textarea class="form-textarea" id="sectionEditorDescription" maxlength="180" placeholder="Tell members what belongs in this section.">${escapeHtml(section?.desc || "")}</textarea>
    </div>
    <div class="form-row" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
      <div class="form-group">
        <label class="form-label">Icon</label>
        <input class="form-input" id="sectionEditorIcon" maxlength="12" value="${escapeHtml(section?.icon || "◈")}" placeholder="💬">
      </div>
      <div class="form-group">
        <label class="form-label">Icon Background</label>
        <input class="form-input" id="sectionEditorIconBg" maxlength="80" value="${escapeHtml(section?.iconBg || "rgba(0,212,255,0.12)")}" placeholder="rgba(0,212,255,0.12)">
      </div>
    </div>
    <div class="form-row" style="display:grid;grid-template-columns:1fr 1fr 140px;gap:12px;">
      <div class="form-group">
        <label class="form-label">Read Access</label>
        <select class="form-input" id="sectionEditorReadRole">${roleOptionsHtml(section?.requiredRole || "new")}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Post Access</label>
        <select class="form-input" id="sectionEditorWriteRole">${roleOptionsHtml(section?.writeRole || "new")}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Sort Order</label>
        <input class="form-input" id="sectionEditorSortOrder" type="number" min="0" max="999" value="${escapeHtml(section?.sortOrder ?? "")}" placeholder="0">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="showSectionManager()">Back</button>
      ${deleteButton}
      <button class="btn btn-primary" onclick="saveSectionEditor(${serializeJsArg(section?.id || "")})">${section ? "Save Section" : "Create Section"}</button>
    </div>
  `, { size: "xl" });

  window.setTimeout(() => document.getElementById("sectionEditorName")?.focus(), 50);
}

function currentSectionPagePath(sectionId) {
  return `section.html?section=${encodeURIComponent(sectionId)}`;
}

function homePagePath() {
  return window.location.pathname.includes("/pages/") ? "../index.html" : "index.html";
}

async function refreshAfterSectionChange(previousId = "", nextId = "", deleted = false) {
  const currentSectionId = queryParam("section");
  const onSectionPage = window.location.pathname.includes("section.html");
  if (onSectionPage && previousId && currentSectionId === previousId) {
    if (deleted) {
      window.location.href = homePagePath();
      return;
    }
    if (nextId && nextId !== previousId) {
      window.location.href = currentSectionPagePath(nextId);
      return;
    }
  }

  if (typeof window.refreshCurrentPage === "function") {
    await window.refreshCurrentPage();
  }
  await showSectionManager();
}

async function saveSectionEditor(sectionId = "") {
  const error = document.getElementById("sectionEditorError");
  if (error) error.classList.remove("visible");
  const payload = {
    name: document.getElementById("sectionEditorName")?.value?.trim() || "",
    slug: document.getElementById("sectionEditorSlug")?.value?.trim() || "",
    categoryId: document.getElementById("sectionEditorCategory")?.value || "",
    description: document.getElementById("sectionEditorDescription")?.value?.trim() || "",
    icon: document.getElementById("sectionEditorIcon")?.value?.trim() || "",
    iconBg: document.getElementById("sectionEditorIconBg")?.value?.trim() || "",
    requiredRole: document.getElementById("sectionEditorReadRole")?.value || "new",
    writeRole: document.getElementById("sectionEditorWriteRole")?.value || "new",
    sortOrder: document.getElementById("sectionEditorSortOrder")?.value?.trim() || "",
  };

  try {
    const data = sectionId
      ? await API.updateSection(sectionId, payload)
      : await API.createSection(payload);
    toast(sectionId ? "Section updated." : "Section created.", "success");
    await refreshAfterSectionChange(sectionId || data.section?.id || "", data.section?.id || "", false);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save that section.";
      error.classList.add("visible");
    }
  }
}

async function confirmDeleteSection(sectionId) {
  const section = sectionManagerState.sections[sectionId];
  const label = section?.name || sectionId;
  if (!window.confirm(`Delete "${label}"? Threads and posts inside it will also be removed.`)) {
    return;
  }

  try {
    await API.deleteSection(sectionId);
    toast("Section deleted.", "success");
    await refreshAfterSectionChange(sectionId, "", true);
  } catch (err) {
    toast(err.message || "Could not delete that section.", "error");
  }
}

function openManagedSection(sectionId) {
  closeModal();
  goToSection(sectionId);
}

async function showStaffInbox(status = "open") {
  if (!Auth.isStaff()) {
    toast("Only moderators and admins can open the staff inbox.", "error");
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Staff Inbox</div>
    <div class="muted-copy">Loading contact notices...</div>
  `, { size: "xl" });

  try {
    const data = await API.getNotices(status);
    const items = data.items || [];
    const counts = data.counts || { open: 0, resolved: 0 };
    const body = items.length
      ? items.map((item) => renderNoticeCard(item)).join("")
      : renderEmptyState("📭", status === "open" ? "No open contact notices." : "No notices in this view.");

    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Staff Inbox</div>
      <div class="sort-tabs notice-filter-tabs">
        <button class="sort-tab ${status === "open" ? "active" : ""}" onclick="showStaffInbox('open')">Open (${counts.open || 0})</button>
        <button class="sort-tab ${status === "resolved" ? "active" : ""}" onclick="showStaffInbox('resolved')">Resolved (${counts.resolved || 0})</button>
        <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showStaffInbox('all')">All</button>
      </div>
      <div class="notice-list">${body}</div>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Staff Inbox</div>
      ${modalError(err.message || "Could not load the contact notices.")}
    `, { size: "lg" });
  }
}

function renderNoticeCard(item) {
  const submittedBy = item.submittedBy
    ? `<button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.submittedBy.id)})">View ${escapeHtml(item.submittedBy.username)}</button>`
      : "";
  const discordRow = item.discordUsername
    ? `<span>Discord: @${escapeHtml(item.discordUsername)}</span>`
    : "<span>No Discord handle shared</span>";
  const handledMeta = item.handledBy
    ? `Reviewed by ${escapeHtml(item.handledBy.username)}${item.handledAt ? ` · ${escapeHtml(formatDateTime(item.handledAt))}` : ""}`
    : "Awaiting review";

  return `
    <div class="notice-card ${item.status === "resolved" ? "resolved" : ""}">
      <div class="notice-head">
        <div>
          <div class="notice-subject">${escapeHtml(item.subject)}</div>
          <div class="notice-meta">
            <span>${escapeHtml(item.name)}</span>
            ${discordRow}
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
          </div>
        </div>
        <span class="badge ${item.status === "resolved" ? "badge-pin" : "badge-hot"}">${item.status === "resolved" ? "Resolved" : "Open"}</span>
      </div>
      <div class="notice-message">${escapeHtml(item.message).replace(/\n/g, "<br>")}</div>
      <div class="detail-list notice-detail-list">
        <div><span>Review Status</span><strong>${escapeHtml(handledMeta)}</strong></div>
      </div>
      <div class="form-group">
        <label class="form-label">Staff Note</label>
        <textarea class="form-textarea notice-note" id="noticeNote-${item.id}" placeholder="Internal note for moderators/admins only.">${escapeHtml(item.adminNote || "")}</textarea>
      </div>
      <div class="notice-actions">
        ${submittedBy}
        ${item.discordUsername ? `<button class="btn btn-outline btn-sm" onclick="copyTextValue(${serializeJsArg(item.discordUsername)}, 'Discord username')">Copy Discord</button>` : ""}
        <button class="btn btn-ghost btn-sm" onclick="saveNotice(${item.id}, '${item.status}')">Save Note</button>
        <button class="btn ${item.status === "resolved" ? "btn-ghost" : "btn-primary"} btn-sm" onclick="saveNotice(${item.id}, '${item.status === "resolved" ? "open" : "resolved"}')">
          ${item.status === "resolved" ? "Reopen" : "Mark Reviewed"}
        </button>
      </div>
    </div>
  `;
}

async function saveNotice(noticeId, status) {
  const note = document.getElementById(`noticeNote-${noticeId}`)?.value || "";
  try {
    await API.updateNotice(noticeId, { status, adminNote: note });
    toast(status === "resolved" ? "Notice marked reviewed." : "Notice updated.", "success");
    await showStaffInbox(status === "resolved" ? "open" : status);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    } else {
      renderNavActions();
      renderSidebarUser();
    }
  } catch (err) {
    toast(err.message || "Could not update that notice.", "error");
  }
}

function moderationActionLabel(type) {
  return {
    warn: "Warning",
    note: "Staff Note",
    timeout: "Timeout",
    clear_timeout: "Timeout Cleared",
    mute: "Mute",
    clear_mute: "Mute Cleared",
    shadow_mute: "Shadow Mute",
    clear_shadow_mute: "Shadow Mute Cleared",
    ban: "Ban",
    unban: "Unban",
    xp_adjust: "XP Adjustment",
    temp_password: "Temporary Password Set",
    role_change: "Role Change",
  }[type] || "Moderation";
}

function renderModerationStatus(moderation) {
  if (!moderation) return "";
  const items = [];
  if (moderation.isBanned) {
    items.push(`
      <div class="moderation-status-card danger">
        <div class="moderation-status-title">Account Banned</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.banReason || "No ban reason recorded.")}</div>
        <div class="tiny-copy">
          ${moderation.bannedAt ? `Issued ${escapeHtml(formatDateTime(moderation.bannedAt))}` : ""}
          ${moderation.bannedBy?.username ? ` by ${escapeHtml(moderation.bannedBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isTimedOut) {
    items.push(`
      <div class="moderation-status-card warn">
        <div class="moderation-status-title">Timed Out</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.timeoutReason || "Posting access is currently restricted.")}</div>
        <div class="tiny-copy">
          Until ${escapeHtml(formatDateTime(moderation.timeoutUntil))}
          ${moderation.timeoutBy?.username ? ` · set by ${escapeHtml(moderation.timeoutBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isMuted) {
    items.push(`
      <div class="moderation-status-card warn">
        <div class="moderation-status-title">Muted</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.muteReason || "Posting and direct messaging are temporarily disabled.")}</div>
        <div class="tiny-copy">
          Until ${escapeHtml(formatDateTime(moderation.muteUntil))}
          ${moderation.muteBy?.username ? ` · set by ${escapeHtml(moderation.muteBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isShadowMuted) {
    items.push(`
      <div class="moderation-status-card info">
        <div class="moderation-status-title">Shadow Muted</div>
        <div class="moderation-status-copy">Staff has enabled a quiet moderation state on this account.</div>
      </div>
    `);
  }
  if (moderation.passwordResetRequired) {
    items.push(`
      <div class="moderation-status-card info">
        <div class="moderation-status-title">Password Reset Required</div>
        <div class="moderation-status-copy">A temporary recovery password is active for this account. The user must choose a new password after their next login.</div>
        <div class="tiny-copy">
          ${moderation.passwordResetSetAt ? `Issued ${escapeHtml(formatDateTime(moderation.passwordResetSetAt))}` : ""}
          ${moderation.passwordResetExpiresAt ? ` · expires ${escapeHtml(formatDateTime(moderation.passwordResetExpiresAt))}` : ""}
          ${moderation.passwordResetBy?.username ? ` by ${escapeHtml(moderation.passwordResetBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (!items.length) {
    items.push(`
      <div class="moderation-status-card ok">
        <div class="moderation-status-title">Account Clear</div>
        <div class="moderation-status-copy">No active timeouts, bans, or mutes on this account.</div>
      </div>
    `);
  }
  return `<div class="moderation-status-stack">${items.join("")}</div>`;
}

function renderModerationHistory(history = []) {
  if (!history.length) {
    return `<div class="centered-message">No moderation history on this account yet.</div>`;
  }
  return history
    .map((item) => {
      const delta = Number(item.deltaXp || 0);
      const xpLine = item.type === "xp_adjust"
        ? `<div class="moderation-history-impact">${delta > 0 ? "+" : ""}${escapeHtml(delta)} XP</div>`
        : "";
      const expiresLine = item.expiresAt
        ? `<div class="tiny-copy">Until ${escapeHtml(formatDateTime(item.expiresAt))}</div>`
        : "";
      const content = item.note || item.reason || "No extra details recorded.";
      return `
        <div class="moderation-history-card">
          <div class="moderation-history-head">
            <div>
              <div class="moderation-history-title">${escapeHtml(moderationActionLabel(item.type))}</div>
              <div class="moderation-history-meta">
                <span>${escapeHtml(item.actor?.username || "Staff")}</span>
                <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
              </div>
            </div>
            ${xpLine}
          </div>
          <div class="moderation-history-copy">${escapeHtml(content)}</div>
          ${expiresLine}
        </div>
      `;
    })
    .join("");
}

function renderSessionAuditList(items = []) {
  if (!items.length) {
    return `<div class="centered-message">No recent session activity is available for this account yet.</div>`;
  }
  return items.map((item) => `
    <div class="moderation-history-card">
      <div class="moderation-history-head">
        <div>
          <div class="moderation-history-title">${escapeHtml(item.userAgent || "Unknown browser")}</div>
          <div class="moderation-history-meta">
            <span>${escapeHtml(item.active ? "Active session" : "Expired session")}</span>
            <span>${escapeHtml(formatDateTime(item.lastSeenAt || item.createdAt))}</span>
          </div>
        </div>
      </div>
      <div class="detail-list notice-detail-list">
        <div><span>IP</span><strong>${escapeHtml(item.lastSeenIp || item.ip || "Unknown")}</strong></div>
        <div><span>Started</span><strong>${escapeHtml(formatDateTime(item.createdAt))}</strong></div>
        <div><span>Expires</span><strong>${escapeHtml(formatDateTime(item.expiresAt))}</strong></div>
      </div>
    </div>
  `).join("");
}

function renderModerationActionOptions(user) {
  const moderation = user.moderation || {};
  const options = [
    { value: "warn", label: "Warn User" },
    { value: "note", label: "Staff Note" },
    { value: "timeout", label: moderation.isTimedOut ? "Update Timeout" : "Timeout User" },
    { value: "mute", label: moderation.isMuted ? "Update Mute" : "Mute User" },
    moderation.isMuted ? { value: "clear_mute", label: "Clear Mute" } : null,
    moderation.isShadowMuted ? { value: "clear_shadow_mute", label: "Clear Shadow Mute" } : { value: "shadow_mute", label: "Shadow Mute User" },
    { value: "xp_adjust", label: "Adjust XP" },
    user.canIssueTempPassword ? { value: "set_temp_password", label: "Set Temp Password" } : null,
    moderation.isTimedOut ? { value: "clear_timeout", label: "Clear Timeout" } : null,
    moderation.isBanned ? { value: "unban", label: "Unban User" } : { value: "ban", label: "Ban User" },
  ].filter(Boolean);
  return options
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

function moderationActionConfig(action) {
  const configs = {
    warn: {
      hint: "Logs a formal warning in the moderation timeline.",
      label: "Warning Reason",
      placeholder: "Explain what rule or behavior triggered this warning.",
      button: "Log Warning",
      showDuration: false,
      showXp: false,
    },
    note: {
      hint: "Internal note for moderators and admins only.",
      label: "Staff Note",
      placeholder: "Add investigation context, follow-up reminders, or staff-only notes.",
      button: "Save Note",
      showDuration: false,
      showXp: false,
    },
    timeout: {
      hint: "Temporarily removes the account's ability to post, edit, delete, or react.",
      label: "Timeout Reason",
      placeholder: "Explain why the account is being timed out.",
      button: "Apply Timeout",
      showDuration: true,
      showXp: false,
    },
    mute: {
      hint: "Temporarily blocks posting and direct messages without applying a full timeout.",
      label: "Mute Reason",
      placeholder: "Explain why the account is being muted.",
      button: "Apply Mute",
      showDuration: true,
      showXp: false,
    },
    clear_timeout: {
      hint: "Restores the user's posting access immediately.",
      label: "Optional Note",
      placeholder: "Optional note about why the timeout was lifted.",
      button: "Clear Timeout",
      showDuration: false,
      showXp: false,
    },
    clear_mute: {
      hint: "Restores the user's posting and messaging access.",
      label: "Optional Note",
      placeholder: "Optional note about why the mute was lifted.",
      button: "Clear Mute",
      showDuration: false,
      showXp: false,
    },
    shadow_mute: {
      hint: "New threads and replies from this account stay hidden from regular readers.",
      label: "Shadow Mute Reason",
      placeholder: "Document why this account is entering silent moderation.",
      button: "Apply Shadow Mute",
      showDuration: false,
      showXp: false,
    },
    clear_shadow_mute: {
      hint: "Stops hiding new content from this account.",
      label: "Optional Note",
      placeholder: "Optional note about why silent moderation was lifted.",
      button: "Clear Shadow Mute",
      showDuration: false,
      showXp: false,
    },
    ban: {
      hint: "Revokes active sessions and blocks the account from logging back in.",
      label: "Ban Reason",
      placeholder: "Explain why this account is being banned.",
      button: "Ban User",
      showDuration: false,
      showXp: false,
    },
    unban: {
      hint: "Restores the user's ability to sign in again.",
      label: "Optional Note",
      placeholder: "Optional note about why the ban was lifted.",
      button: "Lift Ban",
      showDuration: false,
      showXp: false,
    },
    xp_adjust: {
      hint: "Grant or remove XP with an audit trail entry.",
      label: "Reason",
      placeholder: "Explain why XP is being changed.",
      button: "Update XP",
      showDuration: false,
      showXp: true,
      showTempPassword: false,
    },
    set_temp_password: {
      hint: "Replaces the account password, signs out active sessions, and forces the user to set a new password after login.",
      label: "Recovery Note (Optional)",
      placeholder: "Optional internal note about this recovery request.",
      button: "Set Temporary Password",
      showDuration: false,
      showXp: false,
      showTempPassword: true,
    },
  };
  return configs[action] || configs.warn;
}

function updateModerationActionForm() {
  const action = document.getElementById("moderationAction")?.value || "warn";
  const config = moderationActionConfig(action);
  const hint = document.getElementById("moderationActionHint");
  const label = document.getElementById("moderationReasonLabel");
  const reason = document.getElementById("moderationReason");
  const durationGroup = document.getElementById("moderationDurationGroup");
  const xpGroup = document.getElementById("moderationXpGroup");
  const tempPasswordGroup = document.getElementById("moderationTempPasswordGroup");
  const tempPasswordConfirmGroup = document.getElementById("moderationTempPasswordConfirmGroup");
  const tempPasswordExpiryGroup = document.getElementById("moderationTempPasswordExpiryGroup");
  const button = document.getElementById("moderationSubmitButton");

  if (hint) hint.textContent = config.hint;
  if (label) label.textContent = config.label;
  if (reason) reason.placeholder = config.placeholder;
  if (durationGroup) durationGroup.style.display = config.showDuration ? "" : "none";
  if (xpGroup) xpGroup.style.display = config.showXp ? "" : "none";
  if (tempPasswordGroup) tempPasswordGroup.style.display = config.showTempPassword ? "" : "none";
  if (tempPasswordConfirmGroup) tempPasswordConfirmGroup.style.display = config.showTempPassword ? "" : "none";
  if (tempPasswordExpiryGroup) tempPasswordExpiryGroup.style.display = config.showTempPassword ? "" : "none";
  if (button) button.textContent = config.button;
}

async function saveModerationAction(userId) {
  const error = document.getElementById("moderationError");
  if (error) error.classList.remove("visible");

  const action = document.getElementById("moderationAction")?.value || "warn";
  const reason = document.getElementById("moderationReason")?.value?.trim() || "";
  const duration = document.getElementById("moderationDuration")?.value || "";
  const deltaXp = document.getElementById("moderationXpDelta")?.value?.trim() || "";
  const tempPassword = document.getElementById("moderationTempPassword")?.value || "";
  const tempPasswordConfirm = document.getElementById("moderationTempPasswordConfirm")?.value || "";
  const tempPasswordExpires = document.getElementById("moderationTempPasswordExpires")?.value || "48";
  const payload = { action };

  if (action === "note") {
    payload.note = reason;
  } else if (action === "set_temp_password") {
    if (tempPassword !== tempPasswordConfirm) {
      if (error) {
        error.textContent = "Temporary passwords do not match.";
        error.classList.add("visible");
      }
      return;
    }
    payload.tempPassword = tempPassword;
    payload.expiresInHours = Number(tempPasswordExpires || 48);
    if (reason) payload.note = reason;
  } else if (reason) {
    payload.reason = reason;
  }
  if (action === "timeout" || action === "mute") {
    payload.minutes = Number(duration || 0);
  }
  if (action === "xp_adjust") {
    payload.deltaXp = Number(deltaXp || 0);
  }

  try {
    const data = await API.moderateUser(userId, payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Moderation updated.", "success");
    await showProfile(userId);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save that moderation action.";
      error.classList.add("visible");
    }
  }
}

async function saveForcedPasswordReset() {
  const error = document.getElementById("passwordResetError");
  const newPassword = document.getElementById("passwordResetNew")?.value || "";
  const confirm = document.getElementById("passwordResetConfirm")?.value || "";
  if (error) error.classList.remove("visible");

  if (newPassword !== confirm) {
    if (error) {
      error.textContent = "Passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const data = await API.updatePassword({ newPassword });
    Auth.setCurrentUser(data.currentUser || null);
    closeModal(null, true);
    toast(data.message || "Password updated.", "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update your password.";
      error.classList.add("visible");
    }
  }
}

async function showProfile(userId) {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Loading profile...</div>
  `);

  try {
    const data = await API.getUser(userId);
    const user = data.user;
    const viewer = Auth.getCurrentUser();
    const role = DB.roles[user.role] || DB.roles.new;
    const xpData = DB.getXPForNextLevel(user.xp || 0);
    const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
    const canManageRole = Boolean(user.canManageRole);
    const canModerate = Boolean(user.canModerate);
    const moderation = user.moderation || null;
    const showStaffHistory = !!viewer && Auth.isStaff();
    const sessionAudit = user.sessionAudit || [];

    const allowedRoles = Object.values(DB.roles)
      .filter((item) => {
        if (!canManageRole || !viewer) return false;
        if (viewer.role === "owner") return true;
        return item.level <= DB.getRoleLevel("mod");
      })
      .sort((left, right) => right.level - left.level);

    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="profile-header"${user.profileAccent ? ` style="border-color:${escapeHtml(user.profileAccent)}55"` : ""}>
        ${makeAvatar(user, "lg")}
        <div class="profile-username">${escapeHtml(user.username)}</div>
        ${user.profileBadge ? `<div class="profile-custom-badge"${user.profileAccent ? ` style="background:${escapeHtml(user.profileAccent)}1a;color:${escapeHtml(user.profileAccent)}"` : ""}>${escapeHtml(user.profileBadge)}</div>` : ""}
        <div style="margin:6px 0">${roleBadge(user.role)}</div>
        <div class="profile-joined">Member since ${escapeHtml(formatDate(user.joined))}${user.online ? ' · <span class="online-dot"></span> Online' : ""}</div>
        ${user.statusText ? `<div class="tiny-copy" style="margin-top:8px;">${escapeHtml(user.statusText)}</div>` : ""}
      </div>
      <div class="profile-bio">${user.bio ? `"${escapeHtml(user.bio)}"` : "No bio yet."}</div>
      ${user.signature ? `<div class="profile-signature">${renderUserContent(user.signature)}</div>` : ""}
      <div class="profile-stats-grid">
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.posts || 0)}</div>
          <div class="profile-stat-label">Posts</div>
        </div>
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.threads || 0)}</div>
          <div class="profile-stat-label">Threads</div>
        </div>
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.xp || 0)}</div>
          <div class="profile-stat-label">XP</div>
        </div>
      </div>
      <div class="xp-bar-wrap">
        <div class="xp-label">
          <span>${escapeHtml(xpData.label)} Progress</span>
          <span>${progress}%</span>
        </div>
        <div class="xp-bar"><div class="xp-fill" style="width:${progress}%"></div></div>
      </div>
      <div class="detail-list">
        <div><span>Likes Received</span><strong>${fmtNum(user.likesReceived || 0)}</strong></div>
        <div><span>Status</span><strong>${user.online ? "Online" : "Offline"}</strong></div>
        ${moderation ? `<div><span>Restrictions</span><strong>${moderation.isBanned ? "Banned" : moderation.isTimedOut ? "Timed Out" : moderation.isMuted ? "Muted" : moderation.isShadowMuted ? "Shadow Muted" : moderation.passwordResetRequired ? "Reset Required" : "Clear"}</strong></div>` : ""}
      </div>
      ${moderation ? `
        <hr class="divider">
        <div class="page-section-title">Account Status</div>
        ${renderModerationStatus(moderation)}
      ` : ""}
      ${canManageRole ? `
        <hr class="divider">
        <div class="form-group">
          <label class="form-label">Manage Role</label>
          <select class="form-input" id="profileRoleSelect">
            ${allowedRoles
              .map((item) => `<option value="${escapeHtml(item.cssClass)}"${item.cssClass === user.role ? " selected" : ""}>${escapeHtml(item.label)}</option>`)
              .join("")}
          </select>
          <div class="form-hint">Owner can assign any role. Admin can assign up to mod.</div>
        </div>
      ` : ""}
      ${canModerate ? `
        <hr class="divider">
        <div class="page-section-title">Moderation Actions</div>
        <div class="form-error" id="moderationError"></div>
        <div class="moderation-panel">
          <div class="form-group">
            <label class="form-label">Action</label>
            <select class="form-input" id="moderationAction" onchange="updateModerationActionForm()">
              ${renderModerationActionOptions(user)}
            </select>
            <div class="form-hint" id="moderationActionHint"></div>
          </div>
          <div class="form-group" id="moderationDurationGroup">
            <label class="form-label">Duration</label>
            <select class="form-input" id="moderationDuration">
              <option value="60">1 hour</option>
              <option value="720">12 hours</option>
              <option value="1440" selected>1 day</option>
              <option value="4320">3 days</option>
              <option value="10080">7 days</option>
              <option value="43200">30 days</option>
            </select>
          </div>
          <div class="form-group" id="moderationXpGroup">
            <label class="form-label">XP Delta</label>
            <input class="form-input" id="moderationXpDelta" type="number" min="-5000" max="5000" step="1" value="25" placeholder="25 or -25">
            <div class="form-hint">Positive grants XP, negative removes it.</div>
          </div>
          <div class="form-group" id="moderationTempPasswordGroup">
            <label class="form-label">Temporary Password</label>
            <input class="form-input" id="moderationTempPassword" type="password" minlength="8" autocomplete="new-password" placeholder="Temporary recovery password">
            <div class="form-hint">Share this securely with the user. It is stored only as a password hash.</div>
          </div>
          <div class="form-group" id="moderationTempPasswordConfirmGroup">
            <label class="form-label">Confirm Temporary Password</label>
            <input class="form-input" id="moderationTempPasswordConfirm" type="password" minlength="8" autocomplete="new-password" placeholder="Confirm temporary password">
          </div>
          <div class="form-group" id="moderationTempPasswordExpiryGroup">
            <label class="form-label">Temporary Password Expires</label>
            <select class="form-input" id="moderationTempPasswordExpires">
              <option value="24">24 hours</option>
              <option value="48" selected>48 hours</option>
              <option value="72">72 hours</option>
              <option value="168">7 days</option>
            </select>
            <div class="form-hint">Expired temporary passwords cannot be used to log in.</div>
          </div>
          <div class="form-group">
            <label class="form-label" id="moderationReasonLabel">Reason</label>
            <textarea class="form-textarea moderation-textarea" id="moderationReason"></textarea>
          </div>
        </div>
      ` : ""}
      ${showStaffHistory ? `
        <hr class="divider">
        <div class="page-section-title">Moderation History</div>
        <div class="moderation-history-list">${renderModerationHistory(user.moderationHistory || [])}</div>
      ` : ""}
      ${(sessionAudit.length && (viewer?.id === user.id || Auth.isStaff())) ? `
        <hr class="divider">
        <div class="page-section-title">Recent Sessions</div>
        <div class="moderation-history-list">${renderSessionAuditList(sessionAudit)}</div>
      ` : ""}
      <div class="form-actions">
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="showReportModal('user', ${JSON.stringify(user.id)}, ${serializeJsArg(user.username)})">Report</button>` : ""}
        ${user.canMessage ? `<button class="btn btn-outline" onclick="showComposeMessageModal(${JSON.stringify(user.id)}, ${serializeJsArg(user.username)})">Message</button>` : ""}
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="saveUserRelationship(${JSON.stringify(user.id)}, { ignoreContent: ${user.relationship?.ignoreContent ? "false" : "true"}, blockDm: ${user.relationship?.blockDm ? "true" : "false"} })">${user.relationship?.ignoreContent ? "Unignore" : "Ignore"} Content</button>` : ""}
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="saveUserRelationship(${JSON.stringify(user.id)}, { ignoreContent: ${user.relationship?.ignoreContent ? "true" : "false"}, blockDm: ${user.relationship?.blockDm ? "false" : "true"} })">${user.relationship?.blockDm ? "Unblock" : "Block"} DMs</button>` : ""}
        ${viewer?.id === user.id && moderation && (moderation.isBanned || moderation.isTimedOut || moderation.isMuted) ? '<button class="btn btn-outline" onclick="showAppealsQueue(\'all\')">Appeals</button>' : ""}
        ${viewer?.id === user.id ? '<button class="btn btn-ghost" onclick="goToSettingsPage()">Settings</button>' : ""}
        ${canManageRole ? `<button class="btn btn-primary" onclick="saveUserRole(${JSON.stringify(user.id)})">Save Role</button>` : ""}
        ${canModerate ? `<button class="btn btn-danger" id="moderationSubmitButton" onclick="saveModerationAction(${JSON.stringify(user.id)})">Apply Action</button>` : ""}
      </div>
    `, { size: canManageRole || canModerate || showStaffHistory || sessionAudit.length ? "xl" : "lg" });
    if (canModerate) {
      updateModerationActionForm();
    }
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Profile Unavailable</div>
      ${modalError(err.message || "Could not load that profile.")}
    `);
  }
}

function showEditProfileModal() {
  const user = Auth.getCurrentUser();
  if (!user) {
    showLoginModal();
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Edit Profile</div>
    <div class="form-error" id="profileError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="profileUsername" maxlength="24" value="${escapeHtml(user.username || "")}" placeholder="Username">
      <div class="form-hint">3-24 characters using letters, numbers, _ or -.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Bio</label>
      <textarea class="form-textarea" id="profileBio" maxlength="280" placeholder="Tell the forum a little about yourself.">${escapeHtml(user.bio || "")}</textarea>
      <div class="form-hint">Up to 280 characters.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveProfile()">Save Changes</button>
    </div>
  `, { size: "lg" });
}

async function saveProfile() {
  const error = document.getElementById("profileError");
  const username = document.getElementById("profileUsername")?.value || "";
  const bio = document.getElementById("profileBio")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({ username, bio });
    Auth.setCurrentUser(data.currentUser || null);
    closeModal();
    toast(data.message || "Profile updated.", "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your profile.";
      error.classList.add("visible");
    }
  }
}

async function saveUserRole(userId) {
  const select = document.getElementById("profileRoleSelect");
  if (!select) return;
  try {
    await API.updateUserRole(userId, select.value);
    toast("Role updated.", "success");
    await showProfile(userId);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    }
  } catch (err) {
    toast(err.message || "Could not update role.", "error");
  }
}

async function saveUserRelationship(userId, payload) {
  try {
    const data = await API.updateUserRelationship(userId, payload);
    if (data.currentUser) {
      Auth.setCurrentUser(data.currentUser);
    }
    toast(data.message || "Member controls updated.", "success");
    await showProfile(userId);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    }
  } catch (err) {
    toast(err.message || "Could not update member controls.", "error");
  }
}

window.toast = toast;
window.copyTextValue = copyTextValue;
window.openModal = openModal;
window.closeModal = closeModal;
window.makeAvatar = makeAvatar;
window.roleBadge = roleBadge;
window.closeNavMenu = closeNavMenu;
window.toggleNavMenu = toggleNavMenu;
window.goToSettingsPage = goToSettingsPage;
window.renderNavActions = renderNavActions;
window.renderSidebarUser = renderSidebarUser;
window.renderSidebarStats = renderSidebarStats;
window.renderActivityFeed = renderActivityFeed;
window.renderTopMembers = renderTopMembers;
window.renderHeroStats = renderHeroStats;
window.renderTicker = renderTicker;
window.renderFooterYear = renderFooterYear;
window.applySiteConfig = applySiteConfig;
window.loadSiteConfig = loadSiteConfig;
window.getSiteDefaultTheme = getSiteDefaultTheme;
window.handleAuthStateChanged = handleAuthStateChanged;
window.showSearchModal = showSearchModal;
window.scheduleGlobalSearch = scheduleGlobalSearch;
window.showNotifications = showNotifications;
window.showNotificationStatus = showNotificationStatus;
window.showNotificationKind = showNotificationKind;
window.markNotificationAsRead = markNotificationAsRead;
window.markAllNotificationsRead = markAllNotificationsRead;
window.openNotificationTarget = openNotificationTarget;
window.showLoginModal = showLoginModal;
window.showRegisterModal = showRegisterModal;
window.showForcedPasswordResetModal = showForcedPasswordResetModal;
window.doLogin = doLogin;
window.doRegister = doRegister;
window.logoutUser = logoutUser;
window.showSectionManager = showSectionManager;
window.showSectionEditor = showSectionEditor;
window.saveSectionEditor = saveSectionEditor;
window.confirmDeleteSection = confirmDeleteSection;
window.openManagedSection = openManagedSection;
window.showMessages = showMessages;
window.showComposeMessageModal = showComposeMessageModal;
window.sendDirectMessage = sendDirectMessage;
window.replyToDirectMessage = replyToDirectMessage;
window.showReportsQueue = showReportsQueue;
window.saveReportQueueItem = saveReportQueueItem;
window.applyReportMacro = applyReportMacro;
window.addReportInternalNote = addReportInternalNote;
window.bulkUpdateReports = bulkUpdateReports;
window.showAppealsQueue = showAppealsQueue;
window.showAppealComposer = showAppealComposer;
window.submitAppeal = submitAppeal;
window.saveAppealQueueItem = saveAppealQueueItem;
window.showAdminOpsModal = showAdminOpsModal;
window.createAdminBackup = createAdminBackup;
window.showBackupGuide = showBackupGuide;
window.runMediaCleanup = runMediaCleanup;
window.showInstallWizard = showInstallWizard;
window.saveAdminSiteSettings = saveAdminSiteSettings;
window.showAdminExportTools = showAdminExportTools;
window.runAdminExport = runAdminExport;
window.previewAdminImport = previewAdminImport;
window.showStaffWorkflowTools = showStaffWorkflowTools;
window.createStaffMacro = createStaffMacro;
window.toggleStaffMacro = toggleStaffMacro;
window.showAuditLog = showAuditLog;
window.applyAuditFilters = applyAuditFilters;
window.showSignupControls = showSignupControls;
window.saveSignupSettings = saveSignupSettings;
window.createSignupInvite = createSignupInvite;
window.toggleInvite = toggleInvite;
window.reviewSignup = reviewSignup;
window.showPluginManager = showPluginManager;
window.togglePluginState = togglePluginState;
window.restoreTrashItem = restoreTrashItem;
window.showReportModal = showReportModal;
window.submitReport = submitReport;
window.showStaffInbox = showStaffInbox;
window.saveNotice = saveNotice;
window.updateModerationActionForm = updateModerationActionForm;
window.saveModerationAction = saveModerationAction;
window.saveForcedPasswordReset = saveForcedPasswordReset;
window.showProfile = showProfile;
window.showEditProfileModal = showEditProfileModal;
window.saveProfile = saveProfile;
window.saveUserRole = saveUserRole;
window.saveUserRelationship = saveUserRelationship;
