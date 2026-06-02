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
        <div class="section-icon section-icon-lg ${sectionBgClass(currentSection.iconBg)}">${escapeHtml(currentSection.icon)}</div>
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
  button.classList.remove("is-hidden");
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
          <div class="thread-badges thread-badges-tight">${renderThreadBadges(thread)}</div>
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
