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
