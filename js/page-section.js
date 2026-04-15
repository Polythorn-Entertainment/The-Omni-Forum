let currentSection = null;
let currentThreads = [];
let currentTopMembers = [];
let currentPagination = null;
let currentSort = "latest";
let currentSearch = "";
let currentPage = 1;
let newThreadUploads = [];

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

async function refreshCurrentPage() {
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();

  const sectionId = queryParam("section");
  currentSort = queryParam("sort") || "latest";
  currentSearch = queryParam("q") || "";
  currentPage = Math.max(1, Number(queryParam("page") || 1));

  if (!sectionId) {
    renderSectionError("⚠️", "Section not found.", "Choose a section from the homepage.");
    return;
  }

  try {
    const data = await API.getSection(sectionId, {
      q: currentSearch,
      sort: currentSort,
      page: currentPage,
      pageSize: 20,
    });
    currentSection = data.section;
    currentThreads = data.threads || [];
    currentTopMembers = data.topMembers || [];
    currentPagination = data.pagination || null;
    currentPage = Number(currentPagination?.page || currentPage);

    renderNavActions();
    renderSidebarUser();

    document.title = `OmniForum — ${currentSection.name}`;
    document.getElementById("breadSection").textContent = currentSection.name;
    const searchInput = document.getElementById("threadSearch");
    if (searchInput) searchInput.value = currentSearch;
    document.querySelectorAll(".sort-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.sort === currentSort);
    });

    renderSectionHeader();
    renderSectionStats();
    renderTopMembers(currentTopMembers);
    renderThreads(currentThreads);
  } catch (err) {
    if (err.status === 403) {
      renderSectionError("🔒", "This section is restricted.", err.message || "You do not have permission to view it.");
    } else {
      renderSectionError("⚠️", "Could not load this section.", err.message || "Please try again.");
    }
  }
}

function renderSectionError(icon, title, detail) {
  const list = document.getElementById("threadList");
  if (list) list.innerHTML = renderEmptyState(icon, title, detail);
  document.getElementById("sectionHeader").innerHTML = "";
  document.getElementById("sectionStats").innerHTML = "";
  renderTopMembers([]);
}

function renderSectionHeader() {
  const header = document.getElementById("sectionHeader");
  if (!header || !currentSection) return;
  const canPost = Auth.canPost(currentSection);
  const headerActions = [];
  if (!canPost) {
    headerActions.push(`<span class="section-locked-tag">🔒 ${escapeHtml(getPostRequirementLabel(currentSection))}</span>`);
  }
  if (Auth.isAdmin()) {
    headerActions.push(`<button class="btn btn-ghost btn-sm" onclick="showSectionManager(${serializeJsArg(currentSection.id)})">Edit Section</button>`);
  }

  header.innerHTML = `
    <div class="thread-header-top">
      <div class="thread-header-title-row">
        <div class="section-icon section-icon-lg" style="background:${currentSection.iconBg}">${escapeHtml(currentSection.icon)}</div>
        <div>
          <div class="thread-title">${escapeHtml(currentSection.name)}</div>
          <div class="muted-copy">${escapeHtml(currentSection.desc)}</div>
        </div>
      </div>
      ${headerActions.length ? `<div class="stack-actions">${headerActions.join("")}</div>` : ""}
    </div>
    <div class="thread-meta">
      <span class="thread-meta-item">📝 ${fmtNum(currentSection.threads)} threads</span>
      <span class="thread-meta-item">💬 ${fmtNum(currentSection.posts)} posts</span>
      <span class="thread-meta-item">👁 ${escapeHtml(DB.roles[currentSection.requiredRole]?.label || "New")} and up</span>
    </div>
  `;

  const button = document.getElementById("newThreadBtn");
  if (!button) return;
  button.style.display = "";
  button.disabled = false;
  button.title = "";

  if (canPost) {
    button.className = "btn btn-primary btn-sm";
    button.textContent = "+ New Thread";
    button.onclick = () => showNewThreadModal();
    return;
  }

  if (!Auth.getCurrentUser()) {
    button.className = "btn btn-ghost btn-sm";
    button.textContent = "Log In to Post";
    button.title = "You need an account to start a thread.";
    button.onclick = () => showLoginModal();
    return;
  }

  const roleLabel = DB.roles[currentSection.writeRole]?.label || "Member";
  button.className = "btn btn-ghost btn-sm";
  button.textContent = `${roleLabel}+ to Post`;
  button.title = `Only ${roleLabel} and above can start threads here.`;
  button.onclick = () => {
    toast(`Only ${roleLabel} and above can post in ${currentSection.name}.`, "info");
  };
}

function renderSectionStats() {
  const stats = document.getElementById("sectionStats");
  if (!stats || !currentSection) return;
  stats.innerHTML = `
    <li><span>Threads</span><strong>${fmtNum(currentSection.threads)}</strong></li>
    <li><span>Posts</span><strong>${fmtNum(currentSection.posts)}</strong></li>
    <li><span>Read Access</span><strong>${escapeHtml(DB.roles[currentSection.requiredRole]?.label || "New")}</strong></li>
    <li><span>Post Access</span><strong>${escapeHtml(DB.roles[currentSection.writeRole]?.label || "New")}</strong></li>
  `;
}

function syncSectionQuery() {
  replacePageQuery({
    sort: currentSort !== "latest" ? currentSort : "",
    q: currentSearch || "",
    page: currentPage > 1 ? currentPage : "",
  });
}

function sortThreads(by, button) {
  currentSort = by;
  currentPage = 1;
  document.querySelectorAll(".sort-tab").forEach((tab) => tab.classList.remove("active"));
  button?.classList.add("active");
  syncSectionQuery();
  refreshCurrentPage();
}

function filterThreads() {
  currentSearch = document.getElementById("threadSearch")?.value?.trim() || "";
  currentPage = 1;
  syncSectionQuery();
  refreshCurrentPage();
}

function goToSectionPage(page) {
  currentPage = Math.max(1, Number(page || 1));
  syncSectionQuery();
  refreshCurrentPage();
}

function renderThreads(list) {
  const container = document.getElementById("threadList");
  if (!container) return;

  if (!list.length) {
    const message = currentSearch
      ? renderEmptyState("🔎", "No threads match your search.", "Try a shorter title or a different tag.")
      : renderEmptyState("💬", "No threads yet.", Auth.canPost(currentSection) ? "Be the first to start the conversation." : "Log in or level up to post here.");
    container.innerHTML = message;
    return;
  }

  container.innerHTML = `
    ${list.map((thread) => `
      <div class="thread-item ${thread.pinned ? "pinned" : ""} ${thread.hot ? "hot" : ""}" onclick="goToThread(${JSON.stringify(thread.id)})">
        <div>${makeAvatar({ username: thread.authorName, role: thread.authorRole, avatarUrl: thread.authorAvatarUrl }, "sm")}</div>
        <div>
          <div class="thread-info-title">${escapeHtml(thread.title)}</div>
          <div class="thread-info-meta">by ${escapeHtml(thread.authorName)} · ${escapeHtml(formatDate(thread.createdAt))}</div>
          <div class="thread-badges" style="margin-top:4px">${renderThreadBadges(thread)}</div>
          ${(thread.tags || []).length ? `<div class="thread-tags-row">${renderThreadTags(thread.tags)}</div>` : ""}
        </div>
        <div class="thread-replies">
          <div class="thread-reply-num">${fmtNum(thread.replies)}</div>
          <div class="thread-reply-label">REPLIES</div>
        </div>
        <div class="thread-last-post">
          <div>${fmtNum(thread.views)} views</div>
          <div>${escapeHtml(formatRelativeTime(thread.lastPostAt || thread.updatedAt))}</div>
        </div>
      </div>
    `).join("")}
    ${renderPaginationControls(currentPagination, {
      previous: "goToSectionPage(currentPage - 1)",
      next: "goToSectionPage(currentPage + 1)",
    })}
  `;
}

function currentNewThreadDraft() {
  return loadDraft("new-thread", currentSection?.id || queryParam("section") || "");
}

function saveNewThreadDraft() {
  saveDraft("new-thread", currentSection?.id || queryParam("section") || "", {
    title: document.getElementById("newThreadTitle")?.value || "",
    tags: document.getElementById("newThreadTags")?.value || "",
    content: document.getElementById("newThreadContent")?.value || "",
  });
}

function refreshNewThreadPreview() {
  const preview = document.getElementById("newThreadPreview");
  if (!preview) return;
  const title = document.getElementById("newThreadTitle")?.value?.trim() || "Thread preview";
  const content = document.getElementById("newThreadContent")?.value || "";
  const tags = normalizePreviewTags(document.getElementById("newThreadTags")?.value || "");
  preview.innerHTML = `
    <div class="preview-card">
      <div class="preview-card-title">${escapeHtml(title)}</div>
      ${tags.length ? `<div class="thread-tags-row">${renderThreadTags(tags)}</div>` : ""}
      <div class="preview-card-body">${renderUserContent(content, newThreadUploads)}</div>
    </div>
  `;
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
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '**', '**')"><strong>B</strong></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '*', '*')"><em>I</em></button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\`', '\`')">Code</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\n> ', '')">Quote</button>
      <button class="btn btn-ghost btn-sm" type="button" onclick="insertComposerToken(${serializeJsArg(textareaId)}, '\n- ', '')">List</button>
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
  saveNewThreadDraft();
  refreshNewThreadPreview();
}

function bindNewThreadDraftEditor() {
  const title = document.getElementById("newThreadTitle");
  const tags = document.getElementById("newThreadTags");
  const content = document.getElementById("newThreadContent");
  [title, tags, content].forEach((node) => {
    node?.addEventListener("input", () => {
      saveNewThreadDraft();
      refreshNewThreadPreview();
    });
  });
  refreshNewThreadPreview();
}

function clearNewThreadDraftAndForm() {
  clearDraft("new-thread", currentSection?.id || queryParam("section") || "");
  document.getElementById("newThreadTitle").value = "";
  document.getElementById("newThreadTags").value = "";
  document.getElementById("newThreadContent").value = "";
  const media = document.getElementById("newThreadMedia");
  if (media) media.value = "";
  newThreadUploads = [];
  renderNewThreadUploadPreview();
  refreshNewThreadPreview();
}

function renderNewThreadUploadPreview() {
  const container = document.getElementById("newThreadUploadPreview");
  if (!container) return;
  container.innerHTML = renderUploadPreviewList(newThreadUploads, {
    removeAction: "removeNewThreadUpload",
    altAction: "updateNewThreadUploadAlt",
  });
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
}

function updateNewThreadUploadAlt(index, value) {
  if (!newThreadUploads[index]) return;
  newThreadUploads[index].alt = String(value || "").slice(0, 120);
  refreshNewThreadPreview();
}

function showNewThreadModal() {
  if (!Auth.getCurrentUser()) {
    showLoginModal();
    return;
  }

  const draft = currentNewThreadDraft();
  newThreadUploads = [];
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Start a Thread</div>
    <div class="form-error" id="newThreadError"></div>
    <div class="form-group">
      <label class="form-label">Title</label>
      <input class="form-input" id="newThreadTitle" maxlength="120" value="${escapeHtml(draft.title || "")}" placeholder="What do you want to talk about?">
    </div>
    <div class="form-group">
      <label class="form-label">Tags</label>
      <input class="form-input" id="newThreadTags" maxlength="80" value="${escapeHtml(draft.tags || "")}" placeholder="javascript, design, announcement">
      <div class="form-hint">Optional. Up to 5 tags, comma separated.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Opening Post</label>
      ${renderComposerToolbar("newThreadContent")}
      <textarea class="form-textarea" id="newThreadContent" placeholder="Write the first post in the thread, or post with images/GIFs only...">${escapeHtml(draft.content || "")}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Images / GIFs</label>
      <div class="upload-dropzone" id="newThreadDropzone" tabindex="0">Drop images here or use the picker below.</div>
      <input class="form-input" id="newThreadMedia" type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple>
      <div class="form-hint">Optional. Up to ${UPLOAD_LIMITS.postCount} files, ${Math.round(UPLOAD_LIMITS.postBytes / (1024 * 1024))}MB each.</div>
      <div id="newThreadUploadPreview"></div>
    </div>
    <div class="form-group">
      <label class="form-label">Optional Poll</label>
      <input class="form-input" id="newThreadPollQuestion" maxlength="120" placeholder="Poll question">
      <div class="form-row search-filter-grid">
        <input class="form-input" id="newThreadPollOption1" maxlength="80" placeholder="Option 1">
        <input class="form-input" id="newThreadPollOption2" maxlength="80" placeholder="Option 2">
        <input class="form-input" id="newThreadPollOption3" maxlength="80" placeholder="Option 3 (optional)">
        <input class="form-input" id="newThreadPollOption4" maxlength="80" placeholder="Option 4 (optional)">
      </div>
      <label class="checkbox-row settings-checkbox-row">
        <input type="checkbox" id="newThreadPollMultiple">
        <span>Allow multiple choices</span>
      </label>
    </div>
    <div class="form-group">
      <label class="form-label">Preview</label>
      <div id="newThreadPreview"></div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="clearNewThreadDraftAndForm()">Clear Draft</button>
      <button class="btn btn-outline" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitNewThread()">Post Thread</button>
    </div>
  `, { size: "xl" });
  bindNewThreadDraftEditor();
  const mediaInput = document.getElementById("newThreadMedia");
  mediaInput?.addEventListener("change", (event) => handleNewThreadFiles(event.target.files));
  bindDropTarget(document.getElementById("newThreadDropzone"), mediaInput, handleNewThreadFiles);
  renderNewThreadUploadPreview();
}

async function submitNewThread() {
  const error = document.getElementById("newThreadError");
  const title = document.getElementById("newThreadTitle")?.value?.trim() || "";
  const tags = document.getElementById("newThreadTags")?.value?.trim() || "";
  const content = document.getElementById("newThreadContent")?.value?.trim() || "";
  if (error) error.classList.remove("visible");

  try {
    const pollQuestion = document.getElementById("newThreadPollQuestion")?.value?.trim() || "";
    const pollOptions = [
      document.getElementById("newThreadPollOption1")?.value?.trim() || "",
      document.getElementById("newThreadPollOption2")?.value?.trim() || "",
      document.getElementById("newThreadPollOption3")?.value?.trim() || "",
      document.getElementById("newThreadPollOption4")?.value?.trim() || "",
    ].filter(Boolean);
    const poll = pollQuestion ? {
      question: pollQuestion,
      options: pollOptions,
      allowsMultiple: Boolean(document.getElementById("newThreadPollMultiple")?.checked),
    } : null;
    const mediaUploads = newThreadUploads;
    const data = await API.createThread(currentSection.id, { title, tags, content, mediaUploads, poll });
    clearDraft("new-thread", currentSection?.id || queryParam("section") || "");
    newThreadUploads = [];
    closeModal();
    toast("Thread posted.", "success");
    goToThread(data.thread.id);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not post this thread.";
      error.classList.add("visible");
    }
  }
}

window.refreshCurrentPage = refreshCurrentPage;
window.sortThreads = sortThreads;
window.filterThreads = filterThreads;
window.goToSectionPage = goToSectionPage;
window.showNewThreadModal = showNewThreadModal;
window.submitNewThread = submitNewThread;
window.clearNewThreadDraftAndForm = clearNewThreadDraftAndForm;
window.removeNewThreadUpload = removeNewThreadUpload;
window.updateNewThreadUploadAlt = updateNewThreadUploadAlt;
window.insertComposerToken = window.insertComposerToken || insertComposerToken;
