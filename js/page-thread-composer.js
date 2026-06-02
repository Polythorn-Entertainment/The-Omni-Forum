/* Reply composer, uploads, mentions, previews, and submit handling */

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
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
}

function renderComposerToolbar(textareaId) {
  return `
    <div class="composer-toolbar">
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, ${serializeJsArg("**")}, ${serializeJsArg("**")})"><strong>B</strong></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, ${serializeJsArg("*")}, ${serializeJsArg("*")})"><em>I</em></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, ${serializeJsArg("`")}, ${serializeJsArg("`")})">Code</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, ${serializeJsArg("\n> ")}, ${serializeJsArg("")})">Quote</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, ${serializeJsArg("\n- ")}, ${serializeJsArg("")})">List</button>
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
  const sensitive = Boolean(document.getElementById("replySensitive")?.checked);
  preview.innerHTML = `<div class="preview-card-body">${renderUserContent(content, replyUploads, { sensitive, blurMedia: false })}</div>`;
}

function bindReplyDraft() {
  const textarea = document.getElementById("replyContent");
  const sensitive = document.getElementById("replySensitive");
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
  sensitive?.addEventListener("change", () => refreshReplyPreview());
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
      <div class="draft-status${draft.savedAt ? " visible" : ""}" id="replyDraftStatus">${draft.savedAt ? `Recovered draft · saved ${escapeHtml(formatRelativeTime(draft.savedAt))}` : ""}</div>
      <div id="replyMentionMenu" class="mention-suggestion-menu"></div>
      <div class="form-group">
        <label class="form-label">Images / GIFs</label>
        <div class="upload-dropzone" id="replyDropzone" tabindex="0">Drop images here, paste a screenshot, or use the picker below.</div>
        <input class="form-input" id="replyMedia" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
        <div class="form-hint">Optional. Up to ${UPLOAD_LIMITS.postCount} files, ${Math.round(UPLOAD_LIMITS.postBytes / (1024 * 1024))}MB each.</div>
        <div id="replyUploadPreview"></div>
      </div>
      <label class="checkbox-row settings-checkbox-row">
        <input type="checkbox" id="replySensitive">
        <span>Blur these images for members who prefer sensitive media hidden</span>
      </label>
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
  bindPasteImageTarget(document.getElementById("replyContent"), async (uploads) => {
    replyUploads = [...replyUploads, ...uploads].slice(0, UPLOAD_LIMITS.postCount);
    renderReplyUploadPreview();
    refreshReplyPreview();
  }, {
    maxFiles: Math.max(0, UPLOAD_LIMITS.postCount - replyUploads.length),
    maxBytes: UPLOAD_LIMITS.postBytes,
    field: "Reply images",
  });
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
  const mediaSensitive = Boolean(document.getElementById("replySensitive")?.checked);
  if (error) error.classList.remove("visible");

  try {
    const mediaUploads = replyUploads.length ? replyUploads : await readImageUploads(mediaInput?.files, {
      maxFiles: UPLOAD_LIMITS.postCount,
      maxBytes: UPLOAD_LIMITS.postBytes,
      field: "Reply images",
    });
    await API.createPost(currentThread.id, { content, mediaUploads, mediaSensitive });
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
