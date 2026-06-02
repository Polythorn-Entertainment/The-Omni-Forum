function currentNewThreadDraft() {
  return loadDraft("new-thread", currentSection?.id || queryParam("section") || "");
}

function saveNewThreadDraft() {
  const savedAt = new Date().toISOString();
  saveDraft("new-thread", currentSection?.id || queryParam("section") || "", {
    title: document.getElementById("newThreadTitle")?.value || "",
    prefix: document.getElementById("newThreadPrefix")?.value || "",
    tags: document.getElementById("newThreadTags")?.value || "",
    content: document.getElementById("newThreadContent")?.value || "",
    savedAt,
  });
  setNewThreadDraftStatus(`Draft saved ${formatRelativeTime(savedAt)}`);
}

function setNewThreadDraftStatus(message) {
  const node = document.getElementById("newThreadDraftStatus");
  if (!node) return;
  node.textContent = message || "";
  node.classList.toggle("visible", Boolean(message));
  if (newThreadDraftSavedTimer) window.clearTimeout(newThreadDraftSavedTimer);
  if (message) {
    newThreadDraftSavedTimer = window.setTimeout(() => {
      const draft = currentNewThreadDraft();
      node.textContent = draft.savedAt ? `Draft saved ${formatRelativeTime(draft.savedAt)}` : "";
    }, 30000);
  }
}

function refreshNewThreadPreview() {
  const preview = document.getElementById("newThreadPreview");
  if (!preview) return;
  const prefix = document.getElementById("newThreadPrefix")?.value?.trim() || "";
  const title = document.getElementById("newThreadTitle")?.value?.trim() || "Thread preview";
  const content = document.getElementById("newThreadContent")?.value || "";
  const tags = normalizePreviewTags(document.getElementById("newThreadTags")?.value || "");
  const sensitive = Boolean(document.getElementById("newThreadSensitive")?.checked);
  const emptyPost = !content.trim() && !newThreadUploads.length;
  preview.innerHTML = `
    <div class="preview-card">
      <div class="preview-card-title">${prefix ? `<span class="thread-tag thread-prefix-inline">${escapeHtml(prefix)}</span>` : ""}${escapeHtml(title)}</div>
      ${tags.length ? `<div class="thread-tags-row">${renderThreadTags(tags)}</div>` : ""}
      <div class="preview-card-body">${emptyPost ? '<p class="muted-copy">Your opening post preview will appear here as you write or add images.</p>' : renderUserContent(content, newThreadUploads, { sensitive, blurMedia: false })}</div>
    </div>
  `;
}

function updateNewThreadStats() {
  const title = document.getElementById("newThreadTitle")?.value || "";
  const content = document.getElementById("newThreadContent")?.value || "";
  const tags = normalizePreviewTags(document.getElementById("newThreadTags")?.value || "");
  const titleCount = document.getElementById("newThreadTitleCount");
  const contentCount = document.getElementById("newThreadContentCount");
  const uploadCount = document.getElementById("newThreadUploadCount");
  const tagCount = document.getElementById("newThreadTagCount");
  if (titleCount) titleCount.textContent = `${title.trim().length}/120`;
  if (contentCount) {
    const words = content.trim() ? content.trim().split(/\s+/).length : 0;
    contentCount.textContent = `${words} word${words === 1 ? "" : "s"}`;
  }
  if (uploadCount) uploadCount.textContent = `${newThreadUploads.length}/${UPLOAD_LIMITS.postCount}`;
  if (tagCount) tagCount.textContent = `${tags.length}/5 tags`;
}

function normalizePreviewTags(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9_-]/g, ""))
    .filter(Boolean)
    .slice(0, 5);
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

function bindNewThreadDraftEditor() {
  const title = document.getElementById("newThreadTitle");
  const prefix = document.getElementById("newThreadPrefix");
  const tags = document.getElementById("newThreadTags");
  const content = document.getElementById("newThreadContent");
  const sensitive = document.getElementById("newThreadSensitive");
  [title, prefix, tags, content, sensitive].forEach((node) => {
    node?.addEventListener("input", () => {
      saveNewThreadDraft();
      refreshNewThreadPreview();
      updateNewThreadStats();
    });
    node?.addEventListener("change", () => {
      saveNewThreadDraft();
      refreshNewThreadPreview();
      updateNewThreadStats();
    });
  });
  refreshNewThreadPreview();
  updateNewThreadStats();
}

function clearNewThreadDraftAndForm() {
  clearDraft("new-thread", currentSection?.id || queryParam("section") || "");
  document.getElementById("newThreadTitle").value = "";
  if (document.getElementById("newThreadPrefix")) document.getElementById("newThreadPrefix").value = "";
  document.getElementById("newThreadTags").value = "";
  document.getElementById("newThreadContent").value = "";
  const media = document.getElementById("newThreadMedia");
  if (media) media.value = "";
  newThreadUploads = [];
  setNewThreadDraftStatus("");
  renderNewThreadUploadPreview();
  refreshNewThreadPreview();
  updateNewThreadStats();
}

function renderNewThreadUploadPreview() {
  const container = document.getElementById("newThreadUploadPreview");
  if (!container) return;
  container.innerHTML = renderUploadPreviewList(newThreadUploads, {
    removeAction: "removeNewThreadUpload",
    altAction: "updateNewThreadUploadAlt",
  });
  updateNewThreadStats();
}

async function handleNewThreadFiles(files) {
  try {
    const uploads = await readImageUploads(files, {
      maxFiles: Math.max(0, UPLOAD_LIMITS.postCount - newThreadUploads.length),
      maxBytes: UPLOAD_LIMITS.postBytes,
      field: "Thread images",
    });
    newThreadUploads = [...newThreadUploads, ...uploads].slice(0, UPLOAD_LIMITS.postCount);
    renderNewThreadUploadPreview();
    refreshNewThreadPreview();
  } catch (err) {
    toast(err.message || "Could not add those images.", "error");
  }
}

function removeNewThreadUpload(index) {
  newThreadUploads.splice(index, 1);
  renderNewThreadUploadPreview();
  refreshNewThreadPreview();
  updateNewThreadStats();
}

function updateNewThreadUploadAlt(index, value) {
  if (!newThreadUploads[index]) return;
  newThreadUploads[index].alt = String(value || "").slice(0, 120);
  refreshNewThreadPreview();
  updateNewThreadStats();
}

function showNewThreadModal() {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }

  const draft = currentNewThreadDraft();
  newThreadUploads = [];
  const prefixOptions = (currentSection?.threadPrefixes || [])
    .map((item) => `<option value="${escapeHtml(item)}"${item === (draft.prefix || "") ? " selected" : ""}>${escapeHtml(item)}</option>`)
    .join("");
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Start a Thread</div>
    <div class="thread-composer-hero">
      <div class="thread-composer-section-mark ${sectionBgClass(currentSection?.iconBg)}">${escapeHtml(currentSection?.icon || "◈")}</div>
      <div>
        <div class="thread-composer-eyebrow">Posting in ${escapeHtml(currentSection?.name || "this section")}</div>
        <div class="thread-composer-title">Shape the first post, then preview it before publishing.</div>
        <div class="thread-composer-meta">
          <span>Post access: ${escapeHtml(DB.roles[currentSection?.writeRole]?.label || "Member")}+</span>
          <span>Images: ${UPLOAD_LIMITS.postCount} max</span>
          <span>Draft autosaves</span>
        </div>
      </div>
    </div>
    <div class="form-error" id="newThreadError"></div>
    <div class="thread-composer-layout">
      <div class="thread-composer-main">
        <section class="thread-composer-card">
          <div class="thread-composer-card-head">
            <div>
              <div class="thread-composer-card-title">Thread Basics</div>
              <div class="thread-composer-card-copy">Give members a clear reason to click.</div>
            </div>
            <span class="thread-composer-chip" id="newThreadTitleCount">0/120</span>
          </div>
          <div class="form-group">
            <label class="form-label">Title</label>
            <input class="form-input composer-title-input" id="newThreadTitle" maxlength="120" value="${escapeHtml(draft.title || "")}" placeholder="Ask a question, pitch an idea, or start a discussion">
          </div>
          <div class="thread-composer-inline-grid">
            ${prefixOptions ? `
              <div class="form-group">
                <label class="form-label">Prefix</label>
                <select class="form-input" id="newThreadPrefix">
                  <option value="">No prefix</option>
                  ${prefixOptions}
                </select>
              </div>
            ` : ""}
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label" for="newThreadTags">Tags</label>
                <span class="thread-composer-chip" id="newThreadTagCount">0/5 tags</span>
              </div>
              <input class="form-input" id="newThreadTags" maxlength="80" value="${escapeHtml(draft.tags || "")}" placeholder="javascript, design, announcement">
              <div class="form-hint">Optional. Separate tags with commas.</div>
            </div>
          </div>
        </section>

        <section class="thread-composer-card">
          <div class="thread-composer-card-head">
            <div>
              <div class="thread-composer-card-title">Opening Post</div>
              <div class="thread-composer-card-copy">Markdown works here. Paste or drag images directly into the composer.</div>
            </div>
            <span class="thread-composer-chip" id="newThreadContentCount">0 words</span>
          </div>
          ${renderComposerToolbar("newThreadContent")}
          <textarea class="form-textarea thread-composer-textarea" id="newThreadContent" placeholder="Write the first post, add context, or post with images/GIFs only...">${escapeHtml(draft.content || "")}</textarea>
          <div class="draft-status${draft.savedAt ? " visible" : ""}" id="newThreadDraftStatus">${draft.savedAt ? `Recovered draft · saved ${escapeHtml(formatRelativeTime(draft.savedAt))}` : ""}</div>
          ${currentSection?.threadTemplate ? `<div class="thread-composer-template"><strong>Template hint</strong><span>${escapeHtml(currentSection.threadTemplate)}</span></div>` : ""}
        </section>

        <section class="thread-composer-card">
          <div class="thread-composer-card-head">
            <div>
              <div class="thread-composer-card-title">Images / GIFs</div>
              <div class="thread-composer-card-copy">Drop files, paste screenshots, or choose images from your device.</div>
            </div>
            <span class="thread-composer-chip" id="newThreadUploadCount">0/${UPLOAD_LIMITS.postCount}</span>
          </div>
          <div class="upload-dropzone thread-composer-dropzone" id="newThreadDropzone" tabindex="0">
            <div class="thread-composer-drop-icon">⬆</div>
            <div>
              <strong>Drop images here</strong>
              <span>PNG, JPG, GIF, or WebP up to ${Math.round(UPLOAD_LIMITS.postBytes / (1024 * 1024))}MB each.</span>
            </div>
          </div>
          <input class="form-input composer-file-input" id="newThreadMedia" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
          <label class="btn btn-outline btn-sm thread-composer-file-button" for="newThreadMedia">Choose Images</label>
          <div id="newThreadUploadPreview"></div>
          <label class="checkbox-row settings-checkbox-row">
            <input type="checkbox" id="newThreadSensitive">
            <span>Blur these images for members who prefer sensitive media hidden</span>
          </label>
        </section>
      </div>

      <aside class="thread-composer-side">
        <section class="thread-composer-card">
          <div class="thread-composer-card-title">Optional Poll</div>
          <div class="thread-composer-card-copy">Add quick voting if the thread needs a decision.</div>
          <input class="form-input" id="newThreadPollQuestion" maxlength="120" placeholder="Poll question">
          <div class="thread-composer-poll-options">
            <input class="form-input" id="newThreadPollOption1" maxlength="80" placeholder="Option 1">
            <input class="form-input" id="newThreadPollOption2" maxlength="80" placeholder="Option 2">
            <input class="form-input" id="newThreadPollOption3" maxlength="80" placeholder="Option 3 (optional)">
            <input class="form-input" id="newThreadPollOption4" maxlength="80" placeholder="Option 4 (optional)">
          </div>
          <label class="checkbox-row settings-checkbox-row">
            <input type="checkbox" id="newThreadPollMultiple">
            <span>Allow multiple choices</span>
          </label>
        </section>

        <section class="thread-composer-card thread-composer-preview-card">
          <div class="thread-composer-card-head">
            <div>
              <div class="thread-composer-card-title">Live Preview</div>
              <div class="thread-composer-card-copy">What readers will see first.</div>
            </div>
          </div>
          <div id="newThreadPreview"></div>
        </section>
      </div>
    </div>

    <div class="form-actions thread-composer-actions">
      <button class="btn btn-ghost" onclick="clearNewThreadDraftAndForm()">Clear Draft</button>
      <button class="btn btn-outline" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitNewThread()">Post Thread</button>
    </div>
  `, { size: "xl" });
  bindNewThreadDraftEditor();
  const mediaInput = document.getElementById("newThreadMedia");
  mediaInput?.addEventListener("change", (event) => handleNewThreadFiles(event.target.files));
  bindDropTarget(document.getElementById("newThreadDropzone"), mediaInput, handleNewThreadFiles);
  bindPasteImageTarget(document.getElementById("newThreadContent"), async (uploads) => {
    newThreadUploads = [...newThreadUploads, ...uploads].slice(0, UPLOAD_LIMITS.postCount);
    renderNewThreadUploadPreview();
    refreshNewThreadPreview();
  }, {
    maxFiles: Math.max(0, UPLOAD_LIMITS.postCount - newThreadUploads.length),
    maxBytes: UPLOAD_LIMITS.postBytes,
    field: "Thread images",
  });
  renderNewThreadUploadPreview();
}
