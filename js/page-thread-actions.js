/* Thread and post actions, edit modals, moderation, split, and delete flows */

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
    <label class="checkbox-row settings-checkbox-row">
      <input type="checkbox" id="editPostSensitive"${post.mediaSensitive ? " checked" : ""}>
      <span>Mark attached media as sensitive</span>
    </label>
    <div class="form-group">
      <label class="form-label">Preview</label>
      <div id="editPostPreview">${renderUserContent(post.content, post.media, { sensitive: post.mediaSensitive, blurMedia: false })}</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="savePostEdit(${JSON.stringify(post.id)})">Save Changes</button>
    </div>
  `, { size: "xl" });

  document.getElementById("editPostContent")?.addEventListener("input", () => {
    const preview = document.getElementById("editPostPreview");
    if (preview) {
      preview.innerHTML = renderUserContent(
        document.getElementById("editPostContent")?.value || "",
        [],
        { sensitive: Boolean(document.getElementById("editPostSensitive")?.checked), blurMedia: false },
      );
    }
  });
  document.getElementById("editPostSensitive")?.addEventListener("change", () => {
    const preview = document.getElementById("editPostPreview");
    if (preview) {
      preview.innerHTML = renderUserContent(
        document.getElementById("editPostContent")?.value || "",
        [],
        { sensitive: Boolean(document.getElementById("editPostSensitive")?.checked), blurMedia: false },
      );
    }
  });
}

async function savePostEdit(postId) {
  const error = document.getElementById("editPostError");
  const content = document.getElementById("editPostContent")?.value?.trim() || "";
  const title = document.getElementById("editPostTitle")?.value?.trim();
  const mediaSensitive = Boolean(document.getElementById("editPostSensitive")?.checked);
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
    await API.updatePost(postId, { content, title, keepMediaIds, mediaUploads, mediaSensitive });
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
  const prefixOptions = (currentThread.section.threadPrefixes || [])
    .map((item) => `<option value="${escapeHtml(item)}"${item === (currentThread.prefix || "") ? " selected" : ""}>${escapeHtml(item)}</option>`)
    .join("");
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Thread Settings</div>
    <div class="form-error" id="threadSettingsError"></div>
    <div class="form-group">
      <label class="form-label">Title</label>
      <input class="form-input" id="threadSettingsTitle" maxlength="120" value="${escapeHtml(currentThread.title)}">
    </div>
    ${prefixOptions ? `
      <div class="form-group">
        <label class="form-label">Prefix</label>
        <select class="form-input" id="threadSettingsPrefix">
          <option value="">No prefix</option>
          ${prefixOptions}
        </select>
      </div>
    ` : ""}
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
        <label class="checkbox-row"><input type="checkbox" id="threadFeatured"${currentThread.featured ? " checked" : ""}> <span>Feature on the homepage spotlight</span></label>
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
      <div class="form-group">
        <label class="form-label">Staff Notes</label>
        <div class="thread-settings-note-list">
          ${(currentThread.staffNotes || []).length ? currentThread.staffNotes.map((note) => `
            <div class="thread-staff-note">
              <div class="thread-staff-note-meta">${escapeHtml(note.author?.username || "Staff")} · ${escapeHtml(formatDateTime(note.createdAt))}</div>
              <div>${escapeHtml(note.note)}</div>
            </div>
          `).join("") : '<div class="form-hint">No staff notes yet.</div>'}
        </div>
        <textarea class="form-textarea" id="threadStaffNote" maxlength="1200" placeholder="Add a staff-only note for future moderation context."></textarea>
      </div>
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
  const prefix = document.getElementById("threadSettingsPrefix")?.value?.trim() || "";
  const tags = document.getElementById("threadSettingsTags")?.value?.trim() || "";
  const pinned = document.getElementById("threadPinned")?.checked;
  const locked = document.getElementById("threadLocked")?.checked;
  const featured = document.getElementById("threadFeatured")?.checked;
  const solved = Boolean(document.getElementById("threadSolved")?.checked);
  const sectionId = document.getElementById("threadSectionId")?.value?.trim() || "";
  const mergeToThreadId = document.getElementById("threadMergeId")?.value?.trim() || "";
  const pollClosed = document.getElementById("threadPollClosed")?.checked;
  const staffNote = document.getElementById("threadStaffNote")?.value?.trim() || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateThread(currentThread.id, {
      title,
      prefix,
      tags,
      pinned,
      locked,
      featured,
      solved,
      sectionId,
      mergeToThreadId,
      pollClosed,
      staffNote,
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
    const labels = {
      locked: currentThread.locked ? "Thread locked." : "Thread unlocked.",
      pinned: currentThread.pinned ? "Thread pinned." : "Thread unpinned.",
      featured: currentThread.featured ? "Thread featured." : "Thread removed from featured.",
    };
    toast(labels[field] || "Thread updated.", "success");
  } catch (err) {
    toast(err.message || "Could not update thread moderation.", "error");
  }
}

function showSplitThreadModal(postId) {
  if (!currentThread?.canModerate) return;
  const post = currentPosts.find((entry) => entry.id === postId);
  if (!post || post.isThreadStarter) return;
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Split Thread</div>
    <p class="muted-copy">This moves the selected reply and every later reply on this page into a new thread. The original opening post stays here.</p>
    <div class="form-error" id="splitThreadError"></div>
    <div class="form-group">
      <label class="form-label">New Thread Title</label>
      <input class="form-input" id="splitThreadTitle" maxlength="120" value="${escapeHtml(`Split from: ${currentThread.title}`)}">
    </div>
    <div class="form-group">
      <label class="form-label">Destination Section</label>
      <input class="form-input" id="splitThreadSection" value="${escapeHtml(currentThread.section.id)}">
      <div class="form-hint">Use a section slug. Leave as-is to keep it in this section.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Tags</label>
      <input class="form-input" id="splitThreadTags" value="${escapeHtml((currentThread.tags || []).join(", "))}">
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitSplitThread(${JSON.stringify(postId)})">Create Split Thread</button>
    </div>
  `, { size: "lg" });
}

async function submitSplitThread(postId) {
  const error = document.getElementById("splitThreadError");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.splitThread(currentThread.id, {
      postId,
      title: document.getElementById("splitThreadTitle")?.value?.trim() || "",
      sectionId: document.getElementById("splitThreadSection")?.value?.trim() || "",
      tags: document.getElementById("splitThreadTags")?.value?.trim() || "",
    });
    closeModal();
    toast(data.message || "Thread split created.", "success");
    goToThread(data.thread.id);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not split that thread.";
      error.classList.add("visible");
    }
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
