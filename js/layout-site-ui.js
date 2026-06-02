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
