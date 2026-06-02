/* Install wizard and site settings UI */

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
    <div class="settings-tool-grid mt-16">
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
    <div class="page-section-title mt-18">Branding & Homepage</div>
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
    <div class="page-section-title mt-18">Policy & Support Copy</div>
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
    <div class="page-section-title mt-18">SEO & Footer</div>
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
    <div class="page-section-title mt-18">Feature Toggles</div>
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
