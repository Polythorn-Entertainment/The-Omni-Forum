let homeData = {
  categories: [],
  stats: {},
  topMembers: [],
  activity: [],
  announcements: [],
};

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

async function refreshCurrentPage() {
  try {
    const data = await API.getHome();
    homeData = data;
    renderNavActions();
    renderSidebarUser();
    renderSidebarStats(data.stats);
    renderActivityFeed(data.activity);
    renderTopMembers(data.topMembers);
    renderHeroStats(data.stats);
    renderTicker(data.announcements);
    renderTrendingThreads(data.trendingThreads || []);
    renderFooterYear();
    renderForumCategories(data.categories);
  } catch (err) {
    const container = document.getElementById("forumCategories");
    if (container) {
      container.innerHTML = renderEmptyState("⚠️", "Could not load the forum.", err.message || "Please try refreshing the page.");
    }
    toast(err.message || "Could not load the forum.", "error");
  }
}

function renderTrendingThreads(items = []) {
  const container = document.getElementById("trendingThreads");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <section class="trending-thread-panel">
      <div class="trending-thread-head">
        <div class="trending-thread-copy">
          <div class="trending-thread-kicker">Momentum Board</div>
          <h3 class="trending-thread-heading">Trending Threads</h3>
          <p class="trending-thread-subtitle">The conversations pulling the most attention across OmniForum right now.</p>
        </div>
        <button class="btn btn-ghost btn-sm trending-thread-search" onclick="showSearchModal()">Advanced Search</button>
      </div>
      <div class="trending-thread-grid">
        ${items.map((thread) => {
          const author = {
            username: thread.authorName,
            role: thread.authorRole,
            avatarUrl: thread.authorAvatarUrl,
          };
          return `
            <button class="trending-thread-card" onclick="goToThread(${JSON.stringify(thread.id)})">
              <div class="trending-thread-card-top">
                <div class="trending-thread-section-pill">
                  <span class="trending-thread-section-icon" style="background:${escapeHtml(thread.section.iconBg)}">${escapeHtml(thread.section.icon)}</span>
                  <span class="trending-thread-section-name">${escapeHtml(thread.section.name)}</span>
                </div>
                <span class="trending-thread-time">${escapeHtml(formatRelativeTime(thread.updatedAt))}</span>
              </div>
              <div class="trending-thread-title">${escapeHtml(thread.title)}</div>
              <div class="trending-thread-author">
                ${makeAvatar(author, "xs")}
                <div class="trending-thread-author-copy">
                  <strong>${escapeHtml(thread.authorName)}</strong>
                  <span>${escapeHtml(DB.roles[thread.authorRole]?.label || "Member")} · started the thread</span>
                </div>
              </div>
              <div class="thread-badges trending-thread-badges">${renderThreadBadges(thread)}</div>
              <div class="trending-thread-stats">
                <div class="trending-thread-stat">
                  <strong>${fmtNum(thread.replies)}</strong>
                  <span>Replies</span>
                </div>
                <div class="trending-thread-stat">
                  <strong>${fmtNum(thread.views)}</strong>
                  <span>Views</span>
                </div>
                <div class="trending-thread-stat">
                  <strong>${fmtNum((thread.tags || []).length)}</strong>
                  <span>Tags</span>
                </div>
              </div>
            </button>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function renderForumCategories(categories = []) {
  const container = document.getElementById("forumCategories");
  if (!container) return;

  if (!categories.length) {
    container.innerHTML = renderEmptyState("🧱", "The forum structure has not been created yet.");
    return;
  }

  container.innerHTML = categories
    .map((category) => {
      const sections = category.sections
        .map((section) => {
          const canPost = Auth.canPost(section);
          const lockedTag = !section.canView
            ? `<span class="section-locked-tag">🔒 ${escapeHtml(DB.roles[section.requiredRole]?.label || "Member")} required</span>`
            : "";
          const writeRestrictedTag = section.canView && !canPost
            ? `<span class="section-write-tag">✍ ${escapeHtml(getPostRequirementLabel(section))}</span>`
            : "";
          const editButton = section.canManage
            ? `
              <div class="section-admin-actions">
                <button class="btn btn-ghost btn-sm" onclick="openSectionEditorFromHome(${serializeJsArg(section.id)}, event)">Edit</button>
              </div>
            `
            : "";
          const clickAction = section.canView
            ? `onclick="goToSection(${serializeJsArg(section.id)})"`
            : `onclick="toast('You need ${escapeHtml(DB.roles[section.requiredRole]?.label || "Member")} role to open this section.', 'error')"`;
          const lastThread = section.lastThread
            ? `
              <div class="section-last-title">${escapeHtml(section.lastThread.title)}</div>
              <div class="section-last-meta">by ${escapeHtml(section.lastThread.by)} · ${escapeHtml(formatRelativeTime(section.lastThread.updatedAt))}</div>
            `
            : '<div class="section-last-meta">No threads yet</div>';

          return `
            <div class="forum-section${section.canView ? "" : " locked"}" ${clickAction}>
              <div class="section-icon" style="background:${section.iconBg}">${escapeHtml(section.icon)}</div>
              <div class="section-info">
                <div class="section-name">${escapeHtml(section.name)}</div>
                <div class="section-desc">${escapeHtml(section.desc)}${lockedTag}${writeRestrictedTag}</div>
              </div>
              <div class="section-counts">
                <div class="section-count-num">${fmtNum(section.threads)}</div>
                <div class="section-count-label">THREADS</div>
              </div>
              <div class="section-last">
                ${section.canView ? lastThread : '<div class="section-last-meta">Restricted</div>'}
              </div>
              ${editButton}
            </div>
          `;
        })
        .join("");

      return `
        <div class="category-group">
          <div class="category-label">${escapeHtml(category.label)}</div>
          <div class="forum-sections">${sections}</div>
        </div>
      `;
    })
    .join("");
}

function openSectionEditorFromHome(sectionId, clickEvent) {
  clickEvent?.stopPropagation();
  if (!sectionId) return;
  showSectionManager(sectionId);
}

window.openSectionEditorFromHome = openSectionEditorFromHome;
window.refreshCurrentPage = refreshCurrentPage;
