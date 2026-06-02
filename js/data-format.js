/* Formatting and theme application helpers */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNum(value) {
  const amount = Number(value || 0);
  if (amount >= 1000000) return `${(amount / 1000000).toFixed(1)}m`;
  if (amount >= 1000) return `${(amount / 1000).toFixed(1)}k`;
  return String(amount);
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRelativeTime(value) {
  if (!value) return "just now";
  const then = new Date(value).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

function initialsForUser(user) {
  const username = typeof user === "string" ? user : user?.username;
  return (username || "NX").slice(0, 2).toUpperCase();
}

function sectionBgClass(value) {
  const normalized = String(value || "").replace(/\s+/g, "").toLowerCase();
  return {
    "rgba(255,107,107,0.1)": "section-bg-red-10",
    "rgba(255,107,107,0.12)": "section-bg-red-12",
    "rgba(255,107,107,0.15)": "section-bg-red-15",
    "rgba(255,209,102,0.1)": "section-bg-yellow-10",
    "rgba(255,209,102,0.15)": "section-bg-yellow-15",
    "rgba(0,212,255,0.08)": "section-bg-cyan-08",
    "rgba(0,212,255,0.1)": "section-bg-cyan-10",
    "rgba(0,212,255,0.12)": "section-bg-cyan-12",
    "rgba(6,214,160,0.1)": "section-bg-green-10",
    "rgba(123,94,167,0.12)": "section-bg-purple-12",
    "rgba(123,94,167,0.15)": "section-bg-purple-15",
    "rgba(123,94,167,0.2)": "section-bg-purple-20",
  }[normalized] || "section-bg-default";
}

function profileAccentClass(value) {
  return {
    "#00d4ff": "profile-accent-cyan",
    "#7b5ea7": "profile-accent-purple",
    "#ff6b6b": "profile-accent-red",
    "#ffd166": "profile-accent-yellow",
    "#06d6a0": "profile-accent-green",
    "#6b7a94": "profile-accent-slate",
  }[String(value || "").toLowerCase()] || "";
}

function themePreviewClass(id) {
  return `theme-preview-${String(id || "midnight").replace(/[^a-z0-9_-]/gi, "").toLowerCase() || "midnight"}`;
}

function resolveSiteTheme(themeId) {
  return SITE_THEMES[themeId] ? themeId : "midnight";
}

function applySiteTheme(themeId, options = {}) {
  const resolved = resolveSiteTheme(themeId);
  const theme = SITE_THEMES[resolved];
  const root = document.documentElement;
  Object.entries(theme.vars).forEach(([name, value]) => {
    root.style.setProperty(name, value);
  });
  root.dataset.siteTheme = resolved;

  try {
    if (options.storage === "set") {
      window.localStorage.setItem(SITE_THEME_STORAGE_KEY, resolved);
    } else if (options.storage === "clear") {
      window.localStorage.removeItem(SITE_THEME_STORAGE_KEY);
    }
  } catch {
    // Ignore localStorage failures.
  }
  return resolved;
}

function applyInitialSiteTheme() {
  let stored = "midnight";
  try {
    stored = window.localStorage.getItem(SITE_THEME_STORAGE_KEY) || "midnight";
  } catch {
    stored = "midnight";
  }
  applySiteTheme(stored, { storage: "ignore" });
}
