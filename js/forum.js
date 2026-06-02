let currentView = "expanded";

function pageHref(page, params = {}) {
  const prefix = window.location.pathname.includes("/pages/") ? "" : "pages/";
  const query = new URLSearchParams(params);
  return `${prefix}${page}${query.toString() ? `?${query.toString()}` : ""}`;
}

function goToSection(sectionId) {
  window.location.href = pageHref("section.html", { section: sectionId });
}

function goToThread(threadId) {
  window.location.href = pageHref("thread.html", { thread: threadId });
}

function goToPost(threadId, postId) {
  window.location.href = pageHref("thread.html", { thread: threadId, post: postId });
}

function setView(view) {
  currentView = view;
  const categories = document.getElementById("forumCategories");
  if (!categories) return;
  categories.classList.toggle("view-compact", view === "compact");
  document.getElementById("btnExpanded")?.classList.toggle("active", view === "expanded");
  document.getElementById("btnCompact")?.classList.toggle("active", view === "compact");
}

function renderEmptyState(icon, message, detail = "") {
  return `
    <div class="empty-state">
      <div class="empty-icon">${icon}</div>
      <div class="empty-text">${escapeHtml(message)}</div>
      ${detail ? `<div class="empty-subtext">${escapeHtml(detail)}</div>` : ""}
    </div>
  `;
}

function renderThreadBadges(thread) {
  const badges = [];
  if (thread.prefix) badges.push(`<span class="badge badge-pin">${escapeHtml(thread.prefix)}</span>`);
  if (thread.featured) badges.push('<span class="badge badge-featured">★ Featured</span>');
  if (thread.pinned) badges.push('<span class="badge badge-pin">📌 Pinned</span>');
  if (thread.hot) badges.push('<span class="badge badge-hot">🔥 Active</span>');
  if (thread.locked) badges.push('<span class="badge badge-locked">🔒 Locked</span>');
  if (thread.solved) badges.push('<span class="badge badge-new">✓ Solved</span>');
  if (thread.poll) badges.push('<span class="badge badge-pin">📊 Poll</span>');
  if (thread.createdAt && (Date.now() - new Date(thread.createdAt).getTime()) < 86400000) {
    badges.push('<span class="badge badge-new">New</span>');
  }
  return badges.join("");
}

function renderThreadTags(tags = []) {
  return tags
    .map((tag) => `<span class="thread-tag thread-tag-accent">#${escapeHtml(tag)}</span>`)
    .join(" ");
}

function getPostRequirementLabel(section) {
  const requiredRole = section?.writeRole || "new";
  if (!Auth.getCurrentUser() && requiredRole === "new") {
    return "Log in to post";
  }
  return `${DB.roles[requiredRole]?.label || "Member"}+ to post`;
}

window.currentView = currentView;
window.goToSection = goToSection;
window.goToThread = goToThread;
window.goToPost = goToPost;
window.setView = setView;
window.renderEmptyState = renderEmptyState;
window.renderThreadBadges = renderThreadBadges;
window.renderThreadTags = renderThreadTags;
window.getPostRequirementLabel = getPostRequirementLabel;
