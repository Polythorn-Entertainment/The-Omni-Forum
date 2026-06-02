/* Thread page state, loading, draft status, and live refresh scheduling */

let currentThread = null;
let currentPosts = [];
let currentTopMembers = [];
let currentRelatedThreads = [];
let currentPagination = null;
let focusedPostId = null;
let currentPage = 1;
let replyUploads = [];
let replyMentionTimer = null;
let threadLiveRefreshTimer = null;
let replyDraftSavedTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

function threadReplyDraft() {
  return loadDraft("thread-reply", currentThread?.id || queryParam("thread") || "");
}

function saveThreadReplyDraft() {
  const savedAt = new Date().toISOString();
  saveDraft("thread-reply", currentThread?.id || queryParam("thread") || "", {
    content: document.getElementById("replyContent")?.value || "",
    savedAt,
  });
  setReplyDraftStatus(`Draft saved ${formatRelativeTime(savedAt)}`);
}

function clearThreadReplyDraft() {
  clearDraft("thread-reply", currentThread?.id || queryParam("thread") || "");
  setReplyDraftStatus("");
}

function setReplyDraftStatus(message) {
  const node = document.getElementById("replyDraftStatus");
  if (!node) return;
  node.textContent = message || "";
  node.classList.toggle("visible", Boolean(message));
  if (replyDraftSavedTimer) window.clearTimeout(replyDraftSavedTimer);
  if (message) {
    replyDraftSavedTimer = window.setTimeout(() => {
      const draft = threadReplyDraft();
      node.textContent = draft.savedAt ? `Draft saved ${formatRelativeTime(draft.savedAt)}` : "";
    }, 30000);
  }
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
    setPageMetadata({
      title: `OmniForum — ${currentThread.title}`,
      description: `${currentThread.section.name} · ${fmtNum(currentThread.replies || 0)} replies · ${fmtNum(currentThread.views || 0)} views`,
      canonicalPath: `/pages/thread.html?thread=${encodeURIComponent(currentThread.id)}`,
      type: "article",
    });
  } catch (err) {
    renderThreadError(err.status === 403 ? "🔒" : "⚠️", err.status === 403 ? "This thread is restricted." : "Could not load this thread.", err.message || "Please try again.");
    setPageMetadata({
      title: "OmniForum — Thread",
      description: "Read and reply to thread discussions on OmniForum.",
      canonicalPath: `/pages/thread.html${threadId ? `?thread=${encodeURIComponent(threadId)}` : ""}`,
      type: "article",
    });
  }
}

function scheduleThreadLiveRefresh() {
  if (threadLiveRefreshTimer) return;
  threadLiveRefreshTimer = window.setTimeout(async () => {
    threadLiveRefreshTimer = null;
    await refreshCurrentPage();
  }, 900);
}

function renderThreadError(icon, title, detail) {
  document.getElementById("threadHeader").innerHTML = "";
  document.getElementById("threadStats").innerHTML = "";
  document.getElementById("postContainer").innerHTML = renderEmptyState(icon, title, detail);
  document.getElementById("replyArea").innerHTML = "";
  renderTopMembers([]);
  renderRelatedThreads([]);
}
