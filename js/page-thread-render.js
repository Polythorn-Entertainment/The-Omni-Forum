/* Thread header, poll, related threads, and post rendering */

function renderThreadHeader() {
  const header = document.getElementById("threadHeader");
  if (!header || !currentThread) return;

  const actions = [];
  if (Auth.getCurrentUser()) {
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="toggleThreadBookmark()">${currentThread.bookmarkedByViewer ? "Unsave" : "Save"}</button>`);
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="toggleThreadSubscription()">${currentThread.subscribedByViewer ? "Following" : "Follow"}</button>`);
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="showReportModal('thread', ${JSON.stringify(currentThread.id)}, ${serializeJsArg(currentThread.title)})">Report</button>`);
  }
  if (currentThread.canEdit) {
    actions.push('<button class="btn btn-ghost btn-sm" onclick="showThreadSettingsModal()">Edit Thread</button>');
  }
  if (currentThread.canModerate) {
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="toggleThreadModeration('pinned')">${currentThread.pinned ? "Unpin" : "Pin"}</button>`);
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="toggleThreadModeration('locked')">${currentThread.locked ? "Unlock" : "Lock"}</button>`);
    actions.push(`<button class="btn btn-ghost btn-sm" onclick="toggleThreadModeration('featured')">${currentThread.featured ? "Unfeature" : "Feature"}</button>`);
  }
  if (currentThread.canDelete) {
    actions.push('<button class="btn btn-danger btn-sm" onclick="deleteThread()">Delete Thread</button>');
  }

  header.innerHTML = `
    <div class="thread-header-top">
      <div>
        <div class="thread-title">${currentThread.prefix ? `<span class="thread-tag thread-prefix-inline">${escapeHtml(currentThread.prefix)}</span>` : ""}${escapeHtml(currentThread.title)}</div>
        <div class="thread-meta">
          ${renderThreadBadges(currentThread)}
          ${renderThreadTags(currentThread.tags || [])}
        </div>
      </div>
      ${actions.length ? `<div class="thread-toolbar">${actions.join("")}</div>` : ""}
    </div>
    <div class="thread-meta">
      <span class="thread-meta-item">👤 <a class="user-link" onclick="showProfile(${JSON.stringify(currentThread.authorId)})">${escapeHtml(currentThread.authorName)}</a></span>
      <span class="thread-meta-item">📅 ${escapeHtml(formatDateTime(currentThread.createdAt))}</span>
      <span class="thread-meta-item">💬 ${fmtNum(currentThread.replies)} replies</span>
      <span class="thread-meta-item">👁️ ${fmtNum(currentThread.views)} views</span>
      <span class="thread-meta-item">⏱ ${escapeHtml(formatRelativeTime(currentThread.updatedAt))}</span>
    </div>
    ${renderThreadPoll()}
    ${renderThreadStaffNotes()}
  `;
}

function renderThreadStaffNotes() {
  if (!currentThread?.canModerate) return "";
  const notes = currentThread.staffNotes || [];
  return `
    <div class="thread-staff-notes">
      <div class="thread-staff-notes-head">
        <strong>Staff Notes</strong>
        <button class="btn btn-ghost btn-sm" onclick="showThreadSettingsModal()">Add Note</button>
      </div>
      ${notes.length ? notes.slice(0, 3).map((note) => `
        <div class="thread-staff-note">
          <div class="thread-staff-note-meta">${escapeHtml(note.author?.username || "Staff")} · ${escapeHtml(formatRelativeTime(note.createdAt))}</div>
          <div>${escapeHtml(note.note)}</div>
        </div>
      `).join("") : '<div class="tiny-copy">No staff notes yet. Add context in Thread Settings for future moderators.</div>'}
    </div>
  `;
}

function renderThreadStats() {
  const stats = document.getElementById("threadStats");
  if (!stats || !currentThread) return;
  stats.innerHTML = `
    <li><span>Replies</span><strong>${fmtNum(currentThread.replies)}</strong></li>
    <li><span>Views</span><strong>${fmtNum(currentThread.views)}</strong></li>
    <li><span>Started</span><strong>${escapeHtml(formatDate(currentThread.createdAt))}</strong></li>
    <li><span>Status</span><strong>${currentThread.locked ? "Locked" : "Open"}</strong></li>
    <li><span>Solved</span><strong>${currentThread.solved ? "Yes" : "No"}</strong></li>
    ${currentThread.prefix ? `<li><span>Prefix</span><strong>${escapeHtml(currentThread.prefix)}</strong></li>` : ""}
    <li><span>Poll</span><strong>${currentThread.poll ? "Enabled" : "None"}</strong></li>
    <li><span>Saved</span><strong>${currentThread.bookmarkedByViewer ? "Yes" : "No"}</strong></li>
    <li><span>Following</span><strong>${currentThread.subscribedByViewer ? "Yes" : "No"}</strong></li>
  `;
}

function renderThreadPoll() {
  if (!currentThread?.poll) return "";
  const poll = currentThread.poll;
  const multiple = poll.allowsMultiple;
  const viewerCanVote = Boolean(Auth.getCurrentUser()) && !poll.isClosed;
  return `
    <div class="thread-poll-card">
      <div class="thread-poll-head">
        <div>
          <div class="thread-poll-title">${escapeHtml(poll.question)}</div>
          <div class="thread-poll-meta">${fmtNum(poll.totalVotes || 0)} vote${Number(poll.totalVotes || 0) === 1 ? "" : "s"} · ${poll.isClosed ? "Closed" : multiple ? "Choose one or more" : "Choose one"}</div>
        </div>
        ${currentThread.canEdit ? `<button class="btn btn-ghost btn-sm" onclick="togglePollClosed()">${poll.isClosed ? "Reopen Poll" : "Close Poll"}</button>` : ""}
      </div>
      <div class="thread-poll-options">
        ${(poll.options || []).map((option) => {
          const totalVotes = Math.max(1, Number(poll.totalVotes || 0));
          const percent = Math.round((Number(option.votes || 0) / totalVotes) * 100);
          return `
            <label class="thread-poll-option ${option.selectedByViewer ? "selected" : ""}">
              <span class="thread-poll-option-main">
                ${viewerCanVote ? `<input type="${multiple ? "checkbox" : "radio"}" name="threadPollOption" value="${option.id}" ${option.selectedByViewer ? "checked" : ""}>` : ""}
                <span>${escapeHtml(option.label)}</span>
              </span>
              <span class="thread-poll-option-meta">${fmtNum(option.votes || 0)} · ${percent}%</span>
            </label>
          `;
        }).join("")}
      </div>
      ${viewerCanVote ? `
        <div class="form-actions">
          <button class="btn btn-primary btn-sm" onclick="submitThreadPollVote()">Save Vote</button>
        </div>
      ` : ""}
    </div>
  `;
}

function renderRelatedThreads(items = []) {
  const container = document.getElementById("relatedThreads");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = `<div class="centered-message settings-empty-block">No related threads yet.</div>`;
    return;
  }
  container.innerHTML = `
    <div class="settings-thread-list related-thread-list">
      ${items.map((thread) => `
        <button class="settings-thread-card related-thread-card" onclick="goToThread(${JSON.stringify(thread.id)})">
          <div class="settings-thread-title">${escapeHtml(thread.title)}</div>
          <div class="settings-thread-meta">
            <span>${fmtNum(thread.replies)} replies</span>
            <span>${escapeHtml(formatRelativeTime(thread.updatedAt))}</span>
          </div>
        </button>
      `).join("")}
    </div>
  `;
}

function goToThreadPage(page) {
  currentPage = Math.max(1, Number(page || 1));
  focusedPostId = "";
  replacePageQuery({
    page: currentPage > 1 ? currentPage : "",
    post: focusedPostId || "",
  });
  refreshCurrentPage();
}

function renderPosts() {
  const container = document.getElementById("postContainer");
  if (!container) return;
  container.classList.toggle("compact-post-stream", Boolean(Auth.getCurrentUser()?.preferences?.compactPostLayout));
  if (!currentPosts.length) {
    container.innerHTML = renderEmptyState("💬", "No posts yet.");
    return;
  }

  container.innerHTML = `
    ${currentPosts.map((post, index) => {
      const author = post.author;
      const actions = [
        `<button class="post-action ${post.likedByViewer ? "liked" : ""}" onclick="toggleLike(${JSON.stringify(post.id)})">♥ <span id="likes-${post.id}">${fmtNum(post.likes)}</span> Likes</button>`,
        `<button class="post-action" onclick="quotePost(${JSON.stringify(post.id)}, ${serializeJsArg(author.username)})">💬 Quote</button>`,
      ];
      if (post.canMarkAnswer && !post.isThreadStarter) {
        actions.push(`
          <button class="post-action ${post.isAcceptedAnswer ? "liked" : ""}" onclick="toggleAcceptedAnswer(${JSON.stringify(post.id)})">
            ${post.isAcceptedAnswer ? "✓ Accepted" : "Mark Answer"}
          </button>
        `);
      }
      if (post.hasHistory) {
        actions.push(`<button class="post-action" onclick="showPostHistory(${JSON.stringify(post.id)})">🕘 History</button>`);
      }
      if (Auth.getCurrentUser()) {
        actions.push(`<button class="post-action" onclick="showReportModal('post', ${JSON.stringify(post.id)}, ${serializeJsArg(`post by ${author.username}`)})">⚑ Report</button>`);
      }
      if (post.canEdit) {
        actions.push(`<button class="post-action" onclick="showEditPostModal(${JSON.stringify(post.id)})">✏️ Edit</button>`);
      }
      if (post.canDelete) {
        actions.push(`<button class="post-action danger-action" onclick="deletePost(${JSON.stringify(post.id)})">🗑 Delete</button>`);
      }
      if (currentThread.canModerate && !post.isThreadStarter) {
        actions.push(`<button class="post-action" onclick="showSplitThreadModal(${JSON.stringify(post.id)})">↗ Split</button>`);
      }

      const absoluteIndex = Number(currentPagination?.offset || 0) + index + 1;
      return `
        <div class="post" id="post-${post.id}">
          <div class="post-sidebar">
            ${makeAvatar(author, "post")}
            <div class="post-username">${escapeHtml(author.username)}</div>
            ${roleBadge(author.role)}
            <div class="post-user-stats">
              <div class="post-user-stat"><span>Posts</span><strong>${fmtNum(author.posts || 0)}</strong></div>
              <div class="post-user-stat"><span>Threads</span><strong>${fmtNum(author.threads || 0)}</strong></div>
              <div class="post-user-stat"><span>XP</span><strong>${fmtNum(author.xp || 0)}</strong></div>
            </div>
            ${author.online ? '<div><span class="online-dot"></span> <span class="tiny-copy">Online</span></div>' : ""}
          </div>
          <div class="post-main">
            <div class="post-header">
              <span class="post-num">#${absoluteIndex}${post.isThreadStarter ? " · OP" : ""}${post.isAcceptedAnswer ? " · Answer" : ""}${post.shadowHidden ? " · Hidden" : ""}</span>
              <span class="post-date">${escapeHtml(formatDateTime(post.createdAt))}${post.editedAt ? ` · edited ${escapeHtml(formatRelativeTime(post.editedAt))}` : ""}</span>
            </div>
            <div class="post-body">${renderUserContent(post.content, post.media, {
              sensitive: post.mediaSensitive,
              blurMedia: post.mediaSensitive && Auth.getCurrentUser()?.preferences?.blurSensitiveMedia !== false,
            })}</div>
            ${author.signature ? `<div class="post-signature">${renderUserContent(author.signature)}</div>` : ""}
            ${(post.reactions || []).length ? `
              <div class="post-reaction-row">
                ${post.reactions.map((item) => `
                  <button class="post-reaction-pill ${post.viewerReactions?.includes(item.emoji) ? "active" : ""}" onclick="toggleReaction(${JSON.stringify(post.id)}, ${serializeJsArg(item.emoji)})">
                    <span>${item.emoji}</span>
                    <span>${fmtNum(item.count)}</span>
                  </button>
                `).join("")}
              </div>
            ` : ""}
            <div class="post-reaction-row quick-reactions">
              ${(window.ALLOWED_REACTIONS || []).map((emoji) => `
                <button class="post-reaction-pill quick ${post.viewerReactions?.includes(emoji) ? "active" : ""}" onclick="toggleReaction(${JSON.stringify(post.id)}, ${serializeJsArg(emoji)})">${emoji}</button>
              `).join("")}
            </div>
            <div class="post-footer">${actions.join("")}</div>
          </div>
        </div>
      `;
    }).join("")}
    ${renderPaginationControls(currentPagination, {
      previous: "goToThreadPage(currentPage - 1)",
      next: "goToThreadPage(currentPage + 1)",
    })}
  `;
}

function highlightTargetPost() {
  const postId = Number(focusedPostId || 0);
  if (!postId) return;
  window.setTimeout(() => {
    document.querySelectorAll(".post.post-focus").forEach((node) => node.classList.remove("post-focus"));
    const target = document.getElementById(`post-${postId}`);
    if (!target) return;
    target.classList.add("post-focus");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }, 40);
}
