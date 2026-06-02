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
      <div class="page-section-title mt-12">Internal Discussion</div>
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
