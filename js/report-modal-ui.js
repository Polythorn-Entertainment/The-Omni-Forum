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
