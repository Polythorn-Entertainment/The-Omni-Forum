/* Staff workflow macro UI */

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
      <div class="settings-form-grid mt-16">
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
      <div class="moderation-history-list mt-16">
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
