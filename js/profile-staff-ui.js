async function showStaffInbox(status = "open") {
  if (!Auth.isStaff()) {
    toast("Only moderators and admins can open the staff inbox.", "error");
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Staff Inbox</div>
    <div class="muted-copy">Loading contact notices...</div>
  `, { size: "xl" });

  try {
    const data = await API.getNotices(status);
    const items = data.items || [];
    const counts = data.counts || { open: 0, resolved: 0 };
    const body = items.length
      ? items.map((item) => renderNoticeCard(item)).join("")
      : renderEmptyState("📭", status === "open" ? "No open contact notices." : "No notices in this view.");

    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Staff Inbox</div>
      <div class="sort-tabs notice-filter-tabs">
        <button class="sort-tab ${status === "open" ? "active" : ""}" onclick="showStaffInbox('open')">Open (${counts.open || 0})</button>
        <button class="sort-tab ${status === "resolved" ? "active" : ""}" onclick="showStaffInbox('resolved')">Resolved (${counts.resolved || 0})</button>
        <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showStaffInbox('all')">All</button>
      </div>
      <div class="notice-list">${body}</div>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Staff Inbox</div>
      ${modalError(err.message || "Could not load the contact notices.")}
    `, { size: "lg" });
  }
}

function renderNoticeCard(item) {
  const submittedBy = item.submittedBy
    ? `<button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(item.submittedBy.id)})">View ${escapeHtml(item.submittedBy.username)}</button>`
      : "";
  const discordRow = item.discordUsername
    ? `<span>Discord: @${escapeHtml(item.discordUsername)}</span>`
    : "<span>No Discord handle shared</span>";
  const handledMeta = item.handledBy
    ? `Reviewed by ${escapeHtml(item.handledBy.username)}${item.handledAt ? ` · ${escapeHtml(formatDateTime(item.handledAt))}` : ""}`
    : "Awaiting review";

  return `
    <div class="notice-card ${item.status === "resolved" ? "resolved" : ""}">
      <div class="notice-head">
        <div>
          <div class="notice-subject">${escapeHtml(item.subject)}</div>
          <div class="notice-meta">
            <span>${escapeHtml(item.name)}</span>
            ${discordRow}
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
          </div>
        </div>
        <span class="badge ${item.status === "resolved" ? "badge-pin" : "badge-hot"}">${item.status === "resolved" ? "Resolved" : "Open"}</span>
      </div>
      <div class="notice-message">${escapeHtml(item.message).replace(/\n/g, "<br>")}</div>
      <div class="detail-list notice-detail-list">
        <div><span>Review Status</span><strong>${escapeHtml(handledMeta)}</strong></div>
      </div>
      <div class="form-group">
        <label class="form-label">Staff Note</label>
        <textarea class="form-textarea notice-note" id="noticeNote-${item.id}" placeholder="Internal note for moderators/admins only.">${escapeHtml(item.adminNote || "")}</textarea>
      </div>
      <div class="notice-actions">
        ${submittedBy}
        ${item.discordUsername ? `<button class="btn btn-outline btn-sm" onclick="copyTextValue(${serializeJsArg(item.discordUsername)}, 'Discord username')">Copy Discord</button>` : ""}
        <button class="btn btn-ghost btn-sm" onclick="saveNotice(${item.id}, '${item.status}')">Save Note</button>
        <button class="btn ${item.status === "resolved" ? "btn-ghost" : "btn-primary"} btn-sm" onclick="saveNotice(${item.id}, '${item.status === "resolved" ? "open" : "resolved"}')">
          ${item.status === "resolved" ? "Reopen" : "Mark Reviewed"}
        </button>
      </div>
    </div>
  `;
}

async function saveNotice(noticeId, status) {
  const note = document.getElementById(`noticeNote-${noticeId}`)?.value || "";
  try {
    await API.updateNotice(noticeId, { status, adminNote: note });
    toast(status === "resolved" ? "Notice marked reviewed." : "Notice updated.", "success");
    await showStaffInbox(status === "resolved" ? "open" : status);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    } else {
      renderNavActions();
      renderSidebarUser();
    }
  } catch (err) {
    toast(err.message || "Could not update that notice.", "error");
  }
}
