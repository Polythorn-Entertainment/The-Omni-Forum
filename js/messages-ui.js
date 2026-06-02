function renderMessageThreadList(threads = [], selectedThreadId = null) {
  if (!threads.length) {
    return `
      <div class="centered-message dm-thread-empty">
        No conversations yet.
        <div class="empty-subtext">Open a member profile and use Message to start a private chat.</div>
      </div>
    `;
  }

  return threads.map((thread) => {
    const unreadCount = Number(thread.unreadCount || 0);
    const preview = thread.lastMessage?.content || "No messages yet.";
    const time = thread.lastMessage?.createdAt ? formatRelativeTime(thread.lastMessage.createdAt) : "";
    return `
      <button class="dm-thread-row ${selectedThreadId === thread.id ? "active" : ""}" onclick="showMessages(${JSON.stringify(thread.id)})">
        <div class="dm-thread-avatar">${makeAvatar(thread.otherUser, "xs")}</div>
        <div class="dm-thread-main">
          <div class="dm-thread-top">
            <span class="dm-thread-name">${escapeHtml(thread.otherUser.username)}</span>
            ${unreadCount ? `<span class="notice-pill">${unreadCount}</span>` : ""}
          </div>
          <div class="dm-thread-preview">${thread.lastMessage?.fromViewer ? "You: " : ""}${escapeHtml(preview)}</div>
        </div>
        <div class="dm-thread-time">${escapeHtml(time)}</div>
      </button>
    `;
  }).join("");
}

function renderMessageBubbles(messages = []) {
  if (!messages.length) {
    return renderEmptyState("✉️", "No messages yet.", "Send the first message to start this conversation.");
  }

  return messages.map((message) => `
    <div class="dm-message ${message.isMine ? "mine" : "theirs"}">
      <div class="dm-message-meta">
        <button class="dm-message-author" onclick="showProfile(${JSON.stringify(message.sender.id)})">${escapeHtml(message.sender.username)}</button>
        <span>${escapeHtml(formatDateTime(message.createdAt))}${message.isMine && message.readAt ? " · Read" : ""}</span>
      </div>
      <div class="dm-bubble">${escapeHtml(message.content).replace(/\n/g, "<br>")}</div>
    </div>
  `).join("");
}

function renderMessagePanel(thread, messages = []) {
  if (!thread) {
    return `
      <div class="dm-panel dm-panel-empty">
        ${renderEmptyState("💬", "Select a conversation.", "Open any thread on the left, or visit a member profile to start one.")}
      </div>
    `;
  }

  return `
    <div class="dm-panel">
      <div class="dm-panel-header">
        <div class="dm-panel-user">
          ${makeAvatar(thread.otherUser)}
          <div>
            <div class="dm-panel-name">${escapeHtml(thread.otherUser.username)}</div>
            <div class="dm-panel-meta">${roleBadge(thread.otherUser.role)}${thread.otherUser.online ? ' <span class="online-dot"></span>' : ""}</div>
          </div>
        </div>
        <div class="stack-actions">
          <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(thread.otherUser.id)})">View Profile</button>
        </div>
      </div>
      <div class="dm-message-list">${renderMessageBubbles(messages)}</div>
      <div class="form-error" id="dmReplyError"></div>
      <div class="form-group">
        <label class="form-label">Reply</label>
        <textarea class="form-textarea dm-reply-textarea" id="dmReplyBody" placeholder="Write a private message to ${escapeHtml(thread.otherUser.username)}"></textarea>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="replyToDirectMessage(${JSON.stringify(thread.id)})">Send Reply</button>
      </div>
    </div>
  `;
}

function renderMessagesModal(thread, messages = []) {
  const selectedThreadId = thread?.id || null;
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Direct Messages</div>
    <div class="dm-layout">
      <aside class="dm-sidebar">
        <div class="dm-sidebar-copy">Private 1:1 conversations across the forum.</div>
        <div class="dm-thread-list">${renderMessageThreadList(dmState.threads, selectedThreadId)}</div>
      </aside>
      ${renderMessagePanel(thread, messages)}
    </div>
  `;
}

async function showMessages(selectedThreadId = null) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Direct Messages</div>
    <div class="muted-copy">Loading conversations...</div>
  `, { size: "xl" });

  try {
    const data = await API.getMessages();
    dmState.threads = data.threads || [];
    let thread = null;
    let messages = [];
    const fallbackThreadId = selectedThreadId || dmState.threads[0]?.id || null;
    if (fallbackThreadId) {
      const threadData = await API.getMessageThread(fallbackThreadId);
      thread = threadData.thread || null;
      messages = threadData.messages || [];
      dmState.selectedThreadId = thread?.id || null;
      if (thread) {
        dmState.threads = dmState.threads.map((item) => (item.id === thread.id ? { ...item, ...thread } : item));
      }
    } else {
      dmState.selectedThreadId = null;
    }
    openModal(renderMessagesModal(thread, messages), { size: "xl" });
    renderNavActions();
    const reply = document.getElementById("dmReplyBody");
    if (reply) {
      window.setTimeout(() => reply.focus(), 50);
      reply.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && dmState.selectedThreadId) {
          replyToDirectMessage(dmState.selectedThreadId);
        }
      });
    }
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Direct Messages</div>
      ${modalError(err.message || "Could not load your conversations.")}
    `, { size: "lg" });
  }
}

function showComposeMessageModal(userId, username) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  if (Auth.getCurrentUser()?.id === userId) {
    toast("You cannot message yourself.", "error");
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Message ${escapeHtml(username)}</div>
    <div class="muted-copy">This starts a private direct-message thread between the two of you.</div>
    <div class="form-error" id="dmComposeError"></div>
    <div class="form-group">
      <label class="form-label">Message</label>
      <textarea class="form-textarea dm-reply-textarea" id="dmComposeBody" placeholder="Write your message to ${escapeHtml(username)}"></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="sendDirectMessage(${JSON.stringify(userId)})">Send Message</button>
    </div>
  `, { size: "lg" });

  window.setTimeout(() => document.getElementById("dmComposeBody")?.focus(), 50);
}

async function sendDirectMessage(userId) {
  const error = document.getElementById("dmComposeError");
  const content = document.getElementById("dmComposeBody")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.sendMessage({ recipientUserId: userId, content });
    renderNavActions();
    await showMessages(data.thread?.id || null);
    toast(data.message || "Direct message sent.", "success");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not send that message.";
      error.classList.add("visible");
    }
  }
}

async function replyToDirectMessage(threadId) {
  const error = document.getElementById("dmReplyError");
  const content = document.getElementById("dmReplyBody")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.replyToMessage(threadId, { content });
    renderNavActions();
    await showMessages(data.thread?.id || threadId);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not send that reply.";
      error.classList.add("visible");
    }
  }
}
