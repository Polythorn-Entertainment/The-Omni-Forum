function notificationOpenLabel(item) {
  if (item.targetType === "dm_thread") return "Open Message";
  if (item.targetType === "user") return "Open Profile";
  if (item.targetType === "report_queue") return "Open Queue";
  if (item.targetType === "appeal_queue") return "Open Appeals";
  if (item.targetType === "contact_notice") return "Open Staff Inbox";
  if (item.targetType === "registration_queue") return "Open Signups";
  return "Open";
}

function renderNotificationCard(item) {
  const unread = !item.readAt;
  return `
    <div class="notification-card ${unread ? "unread" : ""}">
      <div class="notification-head">
        <div>
          <div class="notification-title">${escapeHtml(item.title)}</div>
          <div class="notification-meta">
            ${item.actor ? `<span>${escapeHtml(item.actor.username)}</span>` : ""}
            <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
          </div>
        </div>
        ${unread ? '<span class="notice-pill">New</span>' : ""}
      </div>
      ${item.body ? `<div class="notification-copy">${escapeHtml(item.body)}</div>` : ""}
      <div class="notification-actions">
        <button class="btn btn-ghost btn-sm" onclick="openNotificationTarget(${JSON.stringify(item.id)})">${notificationOpenLabel(item)}</button>
        ${unread ? `<button class="btn btn-outline btn-sm" onclick="markNotificationAsRead(${JSON.stringify(item.id)})">Mark Read</button>` : ""}
      </div>
    </div>
  `;
}

function notificationKindTabs(counts = {}, kind = "all") {
  const tabs = [
    ["all", "All", counts.unread || 0],
    ["replies", "Replies", counts.replies || 0],
    ["mentions", "Mentions", counts.mentions || 0],
    ["dms", "DMs", counts.dms || 0],
    ["likes", "Likes", counts.likes || 0],
    ["staff_actions", "Staff Actions", counts.staffActions || 0],
  ];
  if (Auth.isStaff()) tabs.push(["staff", "Staff Queues", counts.staff || 0]);
  return `
    <div class="notice-kind-tabs">
      ${tabs.map(([value, label, count]) => `
        <button class="notice-kind-tab ${kind === value ? "active" : ""}" onclick="showNotificationKind(${serializeJsArg(value)})">
          <span>${escapeHtml(label)}</span>
          ${count ? `<strong>${fmtNum(count)}</strong>` : ""}
        </button>
      `).join("")}
    </div>
  `;
}

function renderNotificationsModal(items = [], counts = { unread: 0 }, status = "all", kind = "all") {
  const body = items.length
    ? items.map((item) => renderNotificationCard(item)).join("")
    : renderEmptyState("🔔", status === "unread" ? "No unread alerts." : "No alerts yet.");
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Alerts</div>
    <div class="sort-tabs notice-filter-tabs">
      <button class="sort-tab ${status === "all" ? "active" : ""}" onclick="showNotificationStatus('all')">All</button>
      <button class="sort-tab ${status === "unread" ? "active" : ""}" onclick="showNotificationStatus('unread')">Unread (${counts.unread || 0})</button>
    </div>
    ${notificationKindTabs(counts, kind)}
    ${counts.unread ? `<div class="form-actions notification-toolbar"><button class="btn btn-ghost btn-sm" onclick="markAllNotificationsRead()">Mark All Read</button></div>` : ""}
    <div class="notification-list">${body}</div>
  `;
}

async function showNotifications(status = "all", kind = notificationState.kind || "all") {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Alerts</div>
    <div class="muted-copy">Loading notifications...</div>
  `, { size: "xl" });
  try {
    const data = await API.getNotifications({ status, kind });
    notificationState.items = data.items || [];
    notificationState.status = status;
    notificationState.kind = data.kind || kind || "all";
    renderNavActions();
    openModal(renderNotificationsModal(notificationState.items, data.counts || {}, status, notificationState.kind), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Alerts</div>
      ${modalError(err.message || "Could not load your notifications.")}
    `, { size: "lg" });
  }
}

function showNotificationStatus(status = "all") {
  return showNotifications(status, notificationState.kind || "all");
}

function showNotificationKind(kind = "all") {
  return showNotifications(notificationState.status || "all", kind);
}

async function markNotificationAsRead(notificationId) {
  try {
    await API.markNotificationRead(notificationId);
    await showNotifications(notificationState.status || "all");
  } catch (err) {
    toast(err.message || "Could not update that alert.", "error");
  }
}

async function markAllNotificationsRead() {
  const ids = notificationState.items.filter((item) => !item.readAt).map((item) => item.id);
  if (!ids.length) return;
  try {
    await API.markNotificationsRead({ ids });
    await showNotifications(notificationState.status || "all");
  } catch (err) {
    toast(err.message || "Could not mark alerts as read.", "error");
  }
}

async function openNotificationTarget(notificationId) {
  const item = notificationState.items.find((entry) => entry.id === notificationId);
  if (!item) return;
  if (!item.readAt) {
    try {
      await API.markNotificationRead(notificationId);
    } catch {
      // Best-effort mark-read; navigation should still work.
    }
  }
  renderNavActions();
  if (item.targetType === "thread") {
    closeModal(null, true);
    if (item.metadata?.postId) {
      goToPost(item.metadata.threadId || item.targetId, item.metadata.postId);
      return;
    }
    goToThread(item.targetId);
    return;
  }
  if (item.targetType === "dm_thread") {
    await showMessages(item.targetId);
    return;
  }
  if (item.targetType === "user") {
    await showProfile(item.targetId);
    return;
  }
  if (item.targetType === "report_queue") {
    if (Auth.isStaff()) {
      await showReportsQueue("open");
    }
    return;
  }
  if (item.targetType === "appeal_queue") {
    if (Auth.isStaff()) {
      await showAppealsQueue("open");
    }
    return;
  }
  if (item.targetType === "contact_notice") {
    if (Auth.isStaff()) {
      await showStaffInbox("open");
    }
    return;
  }
  if (item.targetType === "registration_queue") {
    if (Auth.isAdmin()) {
      await showSignupControls();
    }
    return;
  }
  toast("This alert does not have a direct destination yet.", "info");
}
