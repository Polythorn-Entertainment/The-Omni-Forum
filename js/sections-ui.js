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
    <div class="form-row two-col-form-row">
      <div class="form-group">
        <label class="form-label">Icon</label>
        <input class="form-input" id="sectionEditorIcon" maxlength="12" value="${escapeHtml(section?.icon || "◈")}" placeholder="💬">
      </div>
      <div class="form-group">
        <label class="form-label">Icon Background</label>
        <input class="form-input" id="sectionEditorIconBg" maxlength="80" value="${escapeHtml(section?.iconBg || "rgba(0,212,255,0.12)")}" placeholder="rgba(0,212,255,0.12)">
      </div>
    </div>
    <div class="form-row section-admin-row">
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
