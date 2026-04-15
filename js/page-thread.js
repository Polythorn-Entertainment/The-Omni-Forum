let currentThread = null;
let currentPosts = [];
let currentTopMembers = [];
let currentRelatedThreads = [];
let currentPagination = null;
let focusedPostId = null;
let currentPage = 1;
let replyUploads = [];
let replyMentionTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

function threadReplyDraft() {
  return loadDraft("thread-reply", currentThread?.id || queryParam("thread") || "");
}

function saveThreadReplyDraft() {
  saveDraft("thread-reply", currentThread?.id || queryParam("thread") || "", {
    content: document.getElementById("replyContent")?.value || "",
  });
}

function clearThreadReplyDraft() {
  clearDraft("thread-reply", currentThread?.id || queryParam("thread") || "");
}

function applyThreadPayload(data) {
  currentThread = data.thread;
  currentPosts = data.posts || [];
  currentTopMembers = data.topMembers || [];
  currentRelatedThreads = data.relatedThreads || [];
  currentPagination = data.pagination || null;
  currentPage = Number(currentPagination?.page || currentPage || 1);
  replacePageQuery({
    page: currentPage > 1 ? currentPage : "",
    post: focusedPostId || "",
  });
}

async function refreshCurrentPage() {
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();

  const threadId = queryParam("thread");
  focusedPostId = queryParam("post");
  currentPage = Math.max(1, Number(queryParam("page") || 1));
  if (!threadId) {
    renderThreadError("⚠️", "Thread not found.", "Choose a thread from a section page.");
    return;
  }

  try {
    const data = await API.getThread(threadId, {
      page: currentPage,
      pageSize: 20,
      postId: focusedPostId || "",
    });
    applyThreadPayload(data);
    renderNavActions();
    renderSidebarUser();

    document.title = `OmniForum — ${currentThread.title}`;
    document.getElementById("breadSection").textContent = currentThread.section.name;
    document.getElementById("breadSection").href = `section.html?section=${encodeURIComponent(currentThread.section.id)}`;
    document.getElementById("breadThread").textContent = currentThread.title;

    renderThreadHeader();
    renderThreadStats();
    renderPosts();
    highlightTargetPost();
    renderReplyArea();
    renderTopMembers(currentTopMembers);
    renderRelatedThreads(currentRelatedThreads);
  } catch (err) {
    renderThreadError(err.status === 403 ? "🔒" : "⚠️", err.status === 403 ? "This thread is restricted." : "Could not load this thread.", err.message || "Please try again.");
  }
}

function renderThreadError(icon, title, detail) {
  document.getElementById("threadHeader").innerHTML = "";
  document.getElementById("threadStats").innerHTML = "";
  document.getElementById("postContainer").innerHTML = renderEmptyState(icon, title, detail);
  document.getElementById("replyArea").innerHTML = "";
  renderTopMembers([]);
  renderRelatedThreads([]);
}

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
  }
  if (currentThread.canDelete) {
    actions.push('<button class="btn btn-danger btn-sm" onclick="deleteThread()">Delete Thread</button>');
  }

  header.innerHTML = `
    <div class="thread-header-top">
      <div>
        <div class="thread-title">${escapeHtml(currentThread.title)}</div>
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
        actions.push(`<button class="post-action" onclick="deletePost(${JSON.stringify(post.id)})" style="color:var(--accent3)">🗑 Delete</button>`);
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
            <div class="post-body">${renderUserContent(post.content, post.media)}</div>
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

function insertComposerToken(textareaId, before, after = "") {
  const textarea = document.getElementById(textareaId);
  if (!textarea) return;
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const selected = textarea.value.slice(start, end);
  const insertion = `${before}${selected}${after}`;
  textarea.value = `${textarea.value.slice(0, start)}${insertion}${textarea.value.slice(end)}`;
  const nextCaret = start + insertion.length;
  textarea.setSelectionRange(nextCaret, nextCaret);
  textarea.focus();
  saveThreadReplyDraft();
  refreshReplyPreview();
}

function renderComposerToolbar(textareaId) {
  return `
    <div class="composer-toolbar">
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '**', '**')"><strong>B</strong></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '*', '*')"><em>I</em></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\`', '\`')">Code</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\n> ', '')">Quote</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\n- ', '')">List</button>
    </div>
  `;
}

function renderReplyUploadPreview() {
  const container = document.getElementById("replyUploadPreview");
  if (!container) return;
  container.innerHTML = renderUploadPreviewList(replyUploads, {
    removeAction: "removeReplyUpload",
    altAction: "updateReplyUploadAlt",
  });
}

async function handleReplyFiles(files) {
  try {
    const uploads = await readImageUploads(files, {
      maxFiles: Math.max(0, UPLOAD_LIMITS.postCount - replyUploads.length),
      maxBytes: UPLOAD_LIMITS.postBytes,
      field: "Reply images",
    });
    replyUploads = [...replyUploads, ...uploads].slice(0, UPLOAD_LIMITS.postCount);
    renderReplyUploadPreview();
    refreshReplyPreview();
  } catch (err) {
    toast(err.message || "Could not add those images.", "error");
  }
}

function removeReplyUpload(index) {
  replyUploads.splice(index, 1);
  renderReplyUploadPreview();
  refreshReplyPreview();
}

function updateReplyUploadAlt(index, value) {
  if (!replyUploads[index]) return;
  replyUploads[index].alt = String(value || "").slice(0, 120);
  refreshReplyPreview();
}

async function lookupReplyMentions() {
  const textarea = document.getElementById("replyContent");
  const menu = document.getElementById("replyMentionMenu");
  if (!textarea || !menu) return;
  const token = mentionQueryAtCaret(textarea.value, textarea.selectionStart);
  if (!token || token.query.length < 1) {
    menu.innerHTML = "";
    menu.classList.remove("visible");
    return;
  }
  try {
    const data = await API.getUsers({ q: token.query, pageSize: 6 });
    const members = data.members || [];
    if (!members.length) {
      menu.innerHTML = "";
      menu.classList.remove("visible");
      return;
    }
    menu.innerHTML = members.map((member) => `
      <button class="mention-suggestion" type="button" onclick="applyReplyMention(${serializeJsArg(member.username)})">
        ${makeAvatar(member, "xs")}
        <span>${escapeHtml(member.username)}</span>
      </button>
    `).join("");
    menu.classList.add("visible");
  } catch {
    menu.innerHTML = "";
    menu.classList.remove("visible");
  }
}

function scheduleReplyMentionLookup() {
  if (replyMentionTimer) {
    window.clearTimeout(replyMentionTimer);
  }
  replyMentionTimer = window.setTimeout(() => {
    lookupReplyMentions();
  }, 120);
}

function applyReplyMention(username) {
  const textarea = document.getElementById("replyContent");
  const menu = document.getElementById("replyMentionMenu");
  insertMentionAtCaret(textarea, username);
  if (menu) {
    menu.innerHTML = "";
    menu.classList.remove("visible");
  }
  saveThreadReplyDraft();
  refreshReplyPreview();
}

function refreshReplyPreview() {
  const preview = document.getElementById("replyPreview");
  if (!preview) return;
  const content = document.getElementById("replyContent")?.value || "";
  preview.innerHTML = `<div class="preview-card-body">${renderUserContent(content, replyUploads)}</div>`;
}

function bindReplyDraft() {
  const textarea = document.getElementById("replyContent");
  if (!textarea) return;
  const draft = threadReplyDraft();
  if (draft.content && !textarea.value) {
    textarea.value = draft.content;
  }
  textarea.addEventListener("input", () => {
    saveThreadReplyDraft();
    refreshReplyPreview();
    scheduleReplyMentionLookup();
  });
  textarea.addEventListener("click", () => scheduleReplyMentionLookup());
  textarea.addEventListener("keyup", () => scheduleReplyMentionLookup());
  refreshReplyPreview();
}

function renderReplyArea() {
  const area = document.getElementById("replyArea");
  if (!area || !currentThread) return;

  if (currentThread.locked) {
    area.innerHTML = `
      <div class="reply-form centered-message">
        <p>🔒 This thread is locked and no longer accepts replies.</p>
      </div>
    `;
    return;
  }

  if (!Auth.getCurrentUser()) {
    area.innerHTML = `
      <div class="reply-form centered-message">
        <p>You need an account to join the discussion.</p>
        <button class="btn btn-primary" onclick="showLoginModal()">Log In to Reply</button>
      </div>
    `;
    return;
  }

  if (!Auth.canPost(currentThread.section)) {
    area.innerHTML = `
      <div class="reply-form centered-message">
        <p>You need <strong>${escapeHtml(DB.roles[currentThread.section.writeRole]?.label || "Member")}</strong> role to post here.</p>
      </div>
    `;
    return;
  }

  const draft = threadReplyDraft();
  replyUploads = [];
  area.innerHTML = `
    <div class="reply-form">
      <h3>Post a Reply</h3>
      <div class="form-error" id="replyError"></div>
      ${renderComposerToolbar("replyContent")}
      <textarea class="form-textarea" id="replyContent" placeholder="Write your reply, or answer with images/GIFs only...">${escapeHtml(draft.content || "")}</textarea>
      <div id="replyMentionMenu" class="mention-suggestion-menu"></div>
      <div class="form-group">
        <label class="form-label">Images / GIFs</label>
        <div class="upload-dropzone" id="replyDropzone" tabindex="0">Drop images here, paste a screenshot, or use the picker below.</div>
        <input class="form-input" id="replyMedia" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
        <div class="form-hint">Optional. Up to ${UPLOAD_LIMITS.postCount} files, ${Math.round(UPLOAD_LIMITS.postBytes / (1024 * 1024))}MB each.</div>
        <div id="replyUploadPreview"></div>
      </div>
      <div class="form-group">
        <label class="form-label">Preview</label>
        <div id="replyPreview"></div>
      </div>
      <div class="form-row">
        <button class="btn btn-primary" onclick="submitReply()">Post Reply</button>
        <button class="btn btn-ghost" onclick="clearReplyDraft()">Clear Draft</button>
      </div>
    </div>
  `;
  bindReplyDraft();
  const replyMedia = document.getElementById("replyMedia");
  replyMedia?.addEventListener("change", (event) => handleReplyFiles(event.target.files));
  bindDropTarget(document.getElementById("replyDropzone"), replyMedia, handleReplyFiles);
  renderReplyUploadPreview();
}

function clearReplyDraft() {
  clearThreadReplyDraft();
  const textarea = document.getElementById("replyContent");
  if (textarea) textarea.value = "";
  const media = document.getElementById("replyMedia");
  if (media) media.value = "";
  replyUploads = [];
  renderReplyUploadPreview();
  refreshReplyPreview();
}

async function submitReply() {
  const error = document.getElementById("replyError");
  const content = document.getElementById("replyContent")?.value?.trim() || "";
  const mediaInput = document.getElementById("replyMedia");
  if (error) error.classList.remove("visible");

  try {
    const mediaUploads = replyUploads.length ? replyUploads : await readImageUploads(mediaInput?.files, {
      maxFiles: UPLOAD_LIMITS.postCount,
      maxBytes: UPLOAD_LIMITS.postBytes,
      field: "Reply images",
    });
    await API.createPost(currentThread.id, { content, mediaUploads });
    clearThreadReplyDraft();
    replyUploads = [];
    focusedPostId = "";
    const data = await API.getThread(currentThread.id, { page: "last", pageSize: 20 });
    applyThreadPayload(data);
    renderSidebarUser();
    renderThreadHeader();
    renderThreadStats();
    renderPosts();
    renderReplyArea();
    toast("Reply posted.", "success");
    window.setTimeout(() => {
      const lastPost = currentPosts[currentPosts.length - 1];
      document.getElementById(`post-${lastPost?.id || ""}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not post your reply.";
      error.classList.add("visible");
    }
  }
}

async function toggleLike(postId) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }

  try {
    const data = await API.toggleLike(postId);
    const post = currentPosts.find((entry) => entry.id === postId);
    if (post) {
      post.likedByViewer = data.liked;
      post.likes = data.likes;
    }
    renderPosts();
  } catch (err) {
    toast(err.message || "Could not update that like.", "error");
  }
}

async function toggleReaction(postId, emoji) {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }
  try {
    const data = await API.toggleReaction(postId, emoji);
    const post = currentPosts.find((entry) => entry.id === postId);
    if (post) {
      post.reactions = data.reactions || [];
      post.viewerReactions = data.viewerReactions || [];
    }
    renderPosts();
  } catch (err) {
    toast(err.message || "Could not update that reaction.", "error");
  }
}

async function toggleAcceptedAnswer(postId) {
  try {
    const answerPostId = currentThread.answerPostId === postId ? "" : postId;
    const data = await API.updateThread(currentThread.id, {
      title: currentThread.title,
      tags: currentThread.tags,
      answerPostId,
      solved: answerPostId ? true : false,
    });
    currentThread = data.thread || currentThread;
    await refreshCurrentPage();
    toast(answerPostId ? "Accepted answer updated." : "Accepted answer cleared.", "success");
  } catch (err) {
    toast(err.message || "Could not update the accepted answer.", "error");
  }
}

async function submitThreadPollVote() {
  const selectedIds = Array.from(document.querySelectorAll('input[name="threadPollOption"]:checked'))
    .map((node) => Number(node.value))
    .filter((value) => Number.isFinite(value) && value > 0);
  if (!selectedIds.length) {
    toast("Choose an option first.", "error");
    return;
  }
  try {
    const data = await API.voteThreadPoll(currentThread.id, selectedIds);
    currentThread.poll = data.poll;
    renderThreadHeader();
    toast("Vote saved.", "success");
  } catch (err) {
    toast(err.message || "Could not save that vote.", "error");
  }
}

async function togglePollClosed() {
  try {
    const data = await API.updateThread(currentThread.id, {
      title: currentThread.title,
      tags: currentThread.tags,
      pollClosed: !currentThread.poll?.isClosed,
    });
    currentThread = data.thread || currentThread;
    renderThreadHeader();
    renderThreadStats();
    toast(currentThread.poll?.isClosed ? "Poll closed." : "Poll reopened.", "success");
  } catch (err) {
    toast(err.message || "Could not update the poll.", "error");
  }
}

function quotePost(postId, username) {
  const textarea = document.getElementById("replyContent");
  if (!textarea) {
    if (!Auth.getCurrentUser()) showLoginModal();
    return;
  }
  const post = currentPosts.find((entry) => entry.id === postId);
  if (!post) return;
  const snippet = post.content.trim().slice(0, 280);
  textarea.value = `[quote=${username}]\n${snippet}\n[/quote]\n\n`;
  saveThreadReplyDraft();
  refreshReplyPreview();
  textarea.focus();
  textarea.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function toggleThreadBookmark() {
  try {
    const data = await API.toggleThreadBookmark(currentThread.id);
    currentThread = data.thread || currentThread;
    renderThreadHeader();
    renderThreadStats();
    toast(data.message || "Saved thread updated.", "success");
  } catch (err) {
    toast(err.message || "Could not update your saved threads.", "error");
  }
}

async function toggleThreadSubscription() {
  try {
    const data = await API.toggleThreadSubscription(currentThread.id);
    currentThread = data.thread || currentThread;
    renderThreadHeader();
    renderThreadStats();
    toast(data.message || "Thread follow updated.", "success");
  } catch (err) {
    toast(err.message || "Could not update that thread follow.", "error");
  }
}

async function showPostHistory(postId) {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Edit History</div>
    <div class="muted-copy">Loading revisions...</div>
  `, { size: "xl" });

  try {
    const data = await API.getPostHistory(postId);
    const items = data.history || [];
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Edit History</div>
      <div class="moderation-history-list">
        ${items.length ? items.map((item) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(item.editor?.username || "Editor")}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
                  ${item.title ? `<span>Title: ${escapeHtml(item.title)}</span>` : ""}
                </div>
              </div>
            </div>
            <div class="moderation-history-copy">${renderUserContent(item.content)}</div>
            ${item.mediaSummary?.length ? `<div class="tiny-copy">${escapeHtml(item.mediaSummary.length)} image attachment${item.mediaSummary.length === 1 ? "" : "s"} were present in this revision.</div>` : ""}
          </div>
        `).join("") : renderEmptyState("🕘", "No edit history yet.")}
      </div>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Edit History</div>
      <div class="form-error visible">${escapeHtml(err.message || "Could not load post history.")}</div>
    `, { size: "lg" });
  }
}

function showEditPostModal(postId) {
  const post = currentPosts.find((entry) => entry.id === postId);
  if (!post) return;

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">${post.isThreadStarter ? "Edit Opening Post" : "Edit Reply"}</div>
    <div class="form-error" id="editPostError"></div>
    ${post.isThreadStarter ? `
      <div class="form-group">
        <label class="form-label">Thread Title</label>
        <input class="form-input" id="editPostTitle" maxlength="120" value="${escapeHtml(currentThread.title)}">
      </div>
    ` : ""}
    <div class="form-group">
      <label class="form-label">Content</label>
      <textarea class="form-textarea" id="editPostContent">${escapeHtml(post.content)}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Attached Images / GIFs</label>
      ${post.media?.length ? `
        <div class="edit-media-grid">
          ${post.media.map((item) => `
            <label class="edit-media-card">
              <input class="edit-media-toggle" type="checkbox" value="${item.id}" checked>
              <img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.alt || "Forum image")}" loading="lazy">
              <span>Keep</span>
            </label>
          `).join("")}
        </div>
      ` : '<div class="form-hint">This post does not have any attached images yet.</div>'}
    </div>
    <div class="form-group">
      <label class="form-label">Add Images / GIFs</label>
      <input class="form-input" id="editPostMedia" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
      <div class="form-hint">Keep or remove the current media above, then add any new files here.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Preview</label>
      <div id="editPostPreview">${renderUserContent(post.content, post.media)}</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="savePostEdit(${JSON.stringify(post.id)})">Save Changes</button>
    </div>
  `, { size: "xl" });

  document.getElementById("editPostContent")?.addEventListener("input", () => {
    const preview = document.getElementById("editPostPreview");
    if (preview) {
      preview.innerHTML = renderUserContent(document.getElementById("editPostContent")?.value || "");
    }
  });
}

async function savePostEdit(postId) {
  const error = document.getElementById("editPostError");
  const content = document.getElementById("editPostContent")?.value?.trim() || "";
  const title = document.getElementById("editPostTitle")?.value?.trim();
  const keepMediaIds = Array.from(document.querySelectorAll(".edit-media-toggle:checked"))
    .map((node) => Number(node.value))
    .filter((value) => Number.isFinite(value) && value > 0);
  const mediaInput = document.getElementById("editPostMedia");
  if (error) error.classList.remove("visible");

  try {
    const mediaUploads = await readImageUploads(mediaInput?.files, {
      maxFiles: Math.max(0, UPLOAD_LIMITS.postCount - keepMediaIds.length),
      maxBytes: UPLOAD_LIMITS.postBytes,
      field: "Post images",
    });
    await API.updatePost(postId, { content, title, keepMediaIds, mediaUploads });
    closeModal();
    await refreshCurrentPage();
    toast("Post updated.", "success");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save that edit.";
      error.classList.add("visible");
    }
  }
}

function showThreadSettingsModal() {
  if (!currentThread) return;
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Thread Settings</div>
    <div class="form-error" id="threadSettingsError"></div>
    <div class="form-group">
      <label class="form-label">Title</label>
      <input class="form-input" id="threadSettingsTitle" maxlength="120" value="${escapeHtml(currentThread.title)}">
    </div>
    <div class="form-group">
      <label class="form-label">Tags</label>
      <input class="form-input" id="threadSettingsTags" value="${escapeHtml((currentThread.tags || []).join(", "))}" placeholder="design, help, announcement">
    </div>
    <div class="checkbox-stack">
      <label class="checkbox-row"><input type="checkbox" id="threadSolved"${currentThread.solved ? " checked" : ""}> <span>Mark thread as solved</span></label>
    </div>
    ${currentThread.canModerate ? `
      <div class="checkbox-stack">
        <label class="checkbox-row"><input type="checkbox" id="threadPinned"${currentThread.pinned ? " checked" : ""}> <span>Pin this thread</span></label>
        <label class="checkbox-row"><input type="checkbox" id="threadLocked"${currentThread.locked ? " checked" : ""}> <span>Lock replies</span></label>
      </div>
      <div class="form-row search-filter-grid">
        <div class="form-group">
          <label class="form-label">Move to Section</label>
          <input class="form-input" id="threadSectionId" value="${escapeHtml(currentThread.section.id)}" placeholder="section slug">
          <div class="form-hint">Enter a destination section slug to move this thread.</div>
        </div>
        <div class="form-group">
          <label class="form-label">Merge Into Thread</label>
          <input class="form-input" id="threadMergeId" type="number" min="1" placeholder="Destination thread id">
          <div class="form-hint">Moves all replies into another thread and removes this one.</div>
        </div>
      </div>
      ${currentThread.poll ? `
        <div class="checkbox-stack">
          <label class="checkbox-row"><input type="checkbox" id="threadPollClosed"${currentThread.poll.isClosed ? " checked" : ""}> <span>Close poll voting</span></label>
        </div>
      ` : ""}
    ` : ""}
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveThreadSettings()">Save Thread</button>
    </div>
  `, { size: "lg" });
}

async function saveThreadSettings() {
  const error = document.getElementById("threadSettingsError");
  const title = document.getElementById("threadSettingsTitle")?.value?.trim() || "";
  const tags = document.getElementById("threadSettingsTags")?.value?.trim() || "";
  const pinned = document.getElementById("threadPinned")?.checked;
  const locked = document.getElementById("threadLocked")?.checked;
  const solved = Boolean(document.getElementById("threadSolved")?.checked);
  const sectionId = document.getElementById("threadSectionId")?.value?.trim() || "";
  const mergeToThreadId = document.getElementById("threadMergeId")?.value?.trim() || "";
  const pollClosed = document.getElementById("threadPollClosed")?.checked;
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateThread(currentThread.id, {
      title,
      tags,
      pinned,
      locked,
      solved,
      sectionId,
      mergeToThreadId,
      pollClosed,
    });
    if (data.merged && data.thread) {
      toast("Threads merged.", "success");
      goToThread(data.thread.id);
      return;
    }
    currentThread = data.thread;
    closeModal();
    renderThreadHeader();
    renderThreadStats();
    renderReplyArea();
    toast("Thread updated.", "success");
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update this thread.";
      error.classList.add("visible");
    }
  }
}

async function toggleThreadModeration(field) {
  if (!currentThread) return;
  try {
    const payload = { title: currentThread.title, tags: currentThread.tags };
    payload[field] = !currentThread[field];
    const data = await API.updateThread(currentThread.id, payload);
    currentThread = data.thread;
    renderThreadHeader();
    renderThreadStats();
    renderReplyArea();
    toast(field === "locked" ? (currentThread.locked ? "Thread locked." : "Thread unlocked.") : (currentThread.pinned ? "Thread pinned." : "Thread unpinned."), "success");
  } catch (err) {
    toast(err.message || "Could not update thread moderation.", "error");
  }
}

async function deletePost(postId) {
  if (!window.confirm("Delete this reply?")) return;
  try {
    await API.deletePost(postId);
    await refreshCurrentPage();
    toast("Reply deleted.", "success");
  } catch (err) {
    toast(err.message || "Could not delete that reply.", "error");
  }
}

async function deleteThread() {
  if (!window.confirm("Delete this entire thread? This cannot be undone.")) return;
  try {
    await API.deleteThread(currentThread.id);
    toast("Thread deleted.", "success");
    window.location.href = `section.html?section=${encodeURIComponent(currentThread.section.id)}`;
  } catch (err) {
    toast(err.message || "Could not delete this thread.", "error");
  }
}

window.refreshCurrentPage = refreshCurrentPage;
window.submitReply = submitReply;
window.toggleLike = toggleLike;
window.toggleReaction = toggleReaction;
window.toggleAcceptedAnswer = toggleAcceptedAnswer;
window.submitThreadPollVote = submitThreadPollVote;
window.togglePollClosed = togglePollClosed;
window.quotePost = quotePost;
window.toggleThreadBookmark = toggleThreadBookmark;
window.toggleThreadSubscription = toggleThreadSubscription;
window.showPostHistory = showPostHistory;
window.showEditPostModal = showEditPostModal;
window.savePostEdit = savePostEdit;
window.showThreadSettingsModal = showThreadSettingsModal;
window.saveThreadSettings = saveThreadSettings;
window.toggleThreadModeration = toggleThreadModeration;
window.deletePost = deletePost;
window.deleteThread = deleteThread;
window.goToThreadPage = goToThreadPage;
window.clearReplyDraft = clearReplyDraft;
window.insertComposerToken = insertComposerToken;
window.removeReplyUpload = removeReplyUpload;
window.updateReplyUploadAlt = updateReplyUploadAlt;
window.applyReplyMention = applyReplyMention;
