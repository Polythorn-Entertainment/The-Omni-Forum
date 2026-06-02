function renderSearchThreads(threads = []) {
  if (!threads.length) {
    return `<div class="centered-message">No thread matches yet.</div>`;
  }
  return threads.map((thread) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div>
          <div class="search-result-title">${escapeHtml(thread.title)}</div>
          <div class="search-result-meta">in ${escapeHtml(thread.section.name)} · by ${escapeHtml(thread.authorName)} · ${escapeHtml(formatRelativeTime(thread.updatedAt))}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToThread(${JSON.stringify(thread.id)})">Open</button>
      </div>
      <div class="thread-badges">${renderThreadBadges(thread)} ${(thread.tags || []).length ? renderThreadTags(thread.tags) : ""}</div>
    </div>
  `).join("");
}

function renderSearchPosts(posts = []) {
  if (!posts.length) {
    return `<div class="centered-message">No post matches yet.</div>`;
  }
  return posts.map((post) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div>
          <div class="search-result-title">${escapeHtml(post.threadTitle)}</div>
          <div class="search-result-meta">post by ${escapeHtml(post.author.username)} · ${escapeHtml(post.sectionName || post.sectionId || "")} · ${escapeHtml(formatRelativeTime(post.createdAt))}</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="closeModal(null, true); goToPost(${JSON.stringify(post.threadId)}, ${JSON.stringify(post.id)})">Open Post</button>
      </div>
      <div class="search-result-copy">${escapeHtml(post.content)}</div>
    </div>
  `).join("");
}

function renderSearchMembers(members = []) {
  if (!members.length) {
    return `<div class="centered-message">No member matches yet.</div>`;
  }
  return members.map((member) => `
    <div class="search-result-card">
      <div class="search-result-head">
        <div class="search-result-user">
          ${makeAvatar(member, "xs")}
          <div>
            <div class="search-result-title">${escapeHtml(member.username)}</div>
            <div class="search-result-meta">${roleBadge(member.role)} · ${fmtNum(member.posts || 0)} posts</div>
          </div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="showProfile(${JSON.stringify(member.id)})">View</button>
      </div>
      <div class="search-result-copy">${escapeHtml(member.bio || "No bio yet.")}</div>
    </div>
  `).join("");
}

function searchFiltersFromDom() {
  return {
    q: document.getElementById("forumSearchInput")?.value?.trim() || "",
    section: document.getElementById("forumSearchSection")?.value || "",
    author: document.getElementById("forumSearchAuthor")?.value?.trim() || "",
    tag: document.getElementById("forumSearchTag")?.value?.trim() || "",
    solved: document.getElementById("forumSearchSolved")?.value || "all",
    media: document.getElementById("forumSearchMedia")?.value || "all",
    replies: document.getElementById("forumSearchReplies")?.value || "all",
    date: document.getElementById("forumSearchDate")?.value || "all",
    sort: document.getElementById("forumSearchSort")?.value || "relevance",
  };
}

function renderSearchSectionOptions(data = null) {
  const sections = data?.sections || [];
  const selected = data?.filters?.section || "";
  return [
    `<option value="">All sections</option>`,
    ...sections.map((item) => `<option value="${escapeHtml(item.id)}"${item.id === selected ? " selected" : ""}>${escapeHtml(item.name)}</option>`),
  ].join("");
}

function renderSearchModalBody(data = null, query = "") {
  const trimmed = query.trim();
  const filters = data?.filters || searchFiltersFromDom?.() || {};
  const hasActiveFilter = ["section", "author", "tag", "solved", "media", "replies", "date"]
    .some((key) => filters[key] && filters[key] !== "all");
  if (!trimmed && !hasActiveFilter) {
    return renderEmptyState("⌘", "Search the forum.", "Find threads, posts, and members from anywhere.");
  }
  if (trimmed.length > 0 && trimmed.length < 2) {
    return renderEmptyState("🔎", "Keep typing.", "Use at least 2 characters for search.");
  }
  if (!data) {
    return `<div class="centered-message">Searching…</div>`;
  }
  const total = (data.threads?.length || 0) + (data.posts?.length || 0) + (data.members?.length || 0);
  if (!total) {
    return renderEmptyState("🫥", "No matches found.", "Try a shorter term, a username, or a thread keyword.");
  }
  return `
    <div class="search-results-grid">
      <div class="search-results-group">
        <div class="page-section-title">Threads <span>${data.threads?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchThreads(data.threads || [])}</div>
      </div>
      <div class="search-results-group">
        <div class="page-section-title">Posts <span>${data.posts?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchPosts(data.posts || [])}</div>
      </div>
      <div class="search-results-group">
        <div class="page-section-title">Members <span>${data.members?.length || 0}</span></div>
        <div class="search-result-list">${renderSearchMembers(data.members || [])}</div>
      </div>
    </div>
  `;
}

function renderSearchModal(data = null, query = "") {
  const filters = data?.filters || {};
  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Search OmniForum</div>
    <div class="form-group">
      <label class="form-label">Search</label>
      <input class="form-input" id="forumSearchInput" type="text" value="${escapeHtml(query)}" placeholder="Search threads, posts, and members" autocomplete="off">
      <div class="form-hint">Tip: press <strong>/</strong> or <strong>Ctrl/Cmd+K</strong> anywhere to open search.</div>
    </div>
    <div class="form-row search-filter-grid">
      <div class="form-group">
        <label class="form-label">Section</label>
        <select class="form-input" id="forumSearchSection">${renderSearchSectionOptions(data)}</select>
      </div>
      <div class="form-group">
        <label class="form-label">Author</label>
        <input class="form-input" id="forumSearchAuthor" type="text" value="${escapeHtml(filters.author || "")}" placeholder="username">
      </div>
      <div class="form-group">
        <label class="form-label">Tag</label>
        <input class="form-input" id="forumSearchTag" type="text" value="${escapeHtml(filters.tag || "")}" placeholder="support">
      </div>
      <div class="form-group">
        <label class="form-label">Solved</label>
        <select class="form-input" id="forumSearchSolved">
          <option value="all"${(filters.solved || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="solved"${filters.solved === "solved" ? " selected" : ""}>Solved</option>
          <option value="unsolved"${filters.solved === "unsolved" ? " selected" : ""}>Unsolved</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Media</label>
        <select class="form-input" id="forumSearchMedia">
          <option value="all"${(filters.media || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="with_media"${filters.media === "with_media" ? " selected" : ""}>Has images/GIFs</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Replies</label>
        <select class="form-input" id="forumSearchReplies">
          <option value="all"${(filters.replies || "all") === "all" ? " selected" : ""}>Any</option>
          <option value="unanswered"${filters.replies === "unanswered" ? " selected" : ""}>Unanswered</option>
          <option value="answered"${filters.replies === "answered" ? " selected" : ""}>Answered</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Date</label>
        <select class="form-input" id="forumSearchDate">
          <option value="all"${(filters.date || "all") === "all" ? " selected" : ""}>Any time</option>
          <option value="today"${filters.date === "today" ? " selected" : ""}>Past day</option>
          <option value="week"${filters.date === "week" ? " selected" : ""}>Past week</option>
          <option value="month"${filters.date === "month" ? " selected" : ""}>Past month</option>
          <option value="year"${filters.date === "year" ? " selected" : ""}>Past year</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Sort</label>
        <select class="form-input" id="forumSearchSort">
          <option value="relevance"${(filters.sort || "relevance") === "relevance" ? " selected" : ""}>Relevance</option>
          <option value="latest"${filters.sort === "latest" ? " selected" : ""}>Latest</option>
          <option value="trending"${filters.sort === "trending" ? " selected" : ""}>Trending</option>
        </select>
      </div>
    </div>
    <div id="forumSearchResults">${renderSearchModalBody(data, query)}</div>
  `;
}

async function showSearchModal(initialQuery = "") {
  const initialText = typeof initialQuery === "string" ? initialQuery : (initialQuery?.q || "");
  openModal(renderSearchModal({
    filters: typeof initialQuery === "string" ? {} : initialQuery,
    sections: [],
  }, initialText), { size: "xl" });
  const input = document.getElementById("forumSearchInput");
  if (!input) return;
  window.setTimeout(() => {
    input.focus();
    input.select();
  }, 50);
  ["forumSearchInput", "forumSearchSection", "forumSearchAuthor", "forumSearchTag", "forumSearchSolved", "forumSearchMedia", "forumSearchReplies", "forumSearchDate", "forumSearchSort"]
    .map((id) => document.getElementById(id))
    .filter(Boolean)
    .forEach((node) => {
      node.addEventListener("input", () => scheduleGlobalSearch());
      node.addEventListener("change", () => scheduleGlobalSearch());
    });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      scheduleGlobalSearch(true);
    }
  });
  if (initialText.trim().length >= 2) {
    await scheduleGlobalSearch(true);
  }
}

async function performGlobalSearch() {
  const container = document.getElementById("forumSearchResults");
  if (!container) return;
  const filters = searchFiltersFromDom();
  const query = filters.q || "";
  const requestId = ++searchState.requestId;
  container.innerHTML = renderSearchModalBody(null, query);
  const hasActiveFilter = ["section", "author", "tag", "solved", "media", "replies", "date"]
    .some((key) => filters[key] && filters[key] !== "all");
  if (query.trim().length > 0 && query.trim().length < 2) {
    container.innerHTML = renderSearchModalBody(null, query);
    return;
  }
  if (!query.trim() && !hasActiveFilter) {
    container.innerHTML = renderSearchModalBody(null, query);
    return;
  }
  try {
    const data = await API.getSearch(filters);
    if (requestId !== searchState.requestId) return;
    const sectionSelect = document.getElementById("forumSearchSection");
    if (sectionSelect) {
      const currentValue = sectionSelect.value;
      sectionSelect.innerHTML = renderSearchSectionOptions(data);
      sectionSelect.value = currentValue || data.filters?.section || "";
    }
    container.innerHTML = renderSearchModalBody(data, query);
  } catch (err) {
    if (requestId !== searchState.requestId) return;
    container.innerHTML = renderEmptyState("⚠️", "Search failed.", err.message || "Please try again.");
  }
}

async function scheduleGlobalSearch(immediate = false) {
  if (searchState.timer) {
    window.clearTimeout(searchState.timer);
    searchState.timer = null;
  }
  if (immediate) {
    await performGlobalSearch();
    return;
  }
  searchState.timer = window.setTimeout(() => {
    performGlobalSearch();
  }, 180);
}
