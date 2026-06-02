function makeAvatar(user, size = "") {
  if (!user) return "";
  const roleKey = user.role || "new";
  const role = DB.roles[roleKey] || DB.roles.new;
  const sizeClass = size ? ` avatar-${size}` : "";
  const avatarUrl = typeof user === "string" ? "" : user?.avatarUrl || user?.authorAvatarUrl || "";
  const avatarBody = avatarUrl
    ? `<img class="avatar-image" src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(`${user.username || "User"} avatar`)}" loading="lazy">`
    : initialsForUser(user);
  return `<div class="avatar${sizeClass} avatar-${escapeHtml(roleKey)}${avatarUrl ? " avatar-has-image" : ""}">${avatarBody}</div>`;
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
