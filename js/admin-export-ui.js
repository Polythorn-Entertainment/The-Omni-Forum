/* Admin export and import preview UI */

function renderAdminExportTools() {
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Import / Export Tools</div>
    <div class="muted-copy">Admin-readable exports for backups, audits, migrations, and safer restore planning. Import preview never writes live data.</div>
    <div class="settings-form-grid mt-16">
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
    <div class="page-section-title mt-18">Import Preview</div>
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
        <div class="settings-tool-card mt-14">
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
