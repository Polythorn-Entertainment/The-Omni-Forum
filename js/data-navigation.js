/* Mention, URL, metadata, and pagination helpers */

function mentionQueryAtCaret(text, selectionStart) {
  const before = String(text || "").slice(0, Math.max(0, Number(selectionStart || 0)));
  const match = before.match(/(^|\s)@([A-Za-z0-9_-]{1,24})$/);
  if (!match) return null;
  return {
    query: match[2],
    start: before.length - match[2].length - 1,
    end: before.length,
  };
}

function insertMentionAtCaret(textarea, username) {
  if (!textarea) return;
  const caret = textarea.selectionStart || 0;
  const token = mentionQueryAtCaret(textarea.value, caret);
  if (!token) return;
  const before = textarea.value.slice(0, token.start);
  const after = textarea.value.slice(token.end);
  const insertion = `@${username} `;
  textarea.value = `${before}${insertion}${after}`;
  const nextCaret = before.length + insertion.length;
  textarea.setSelectionRange(nextCaret, nextCaret);
  textarea.focus();
}

function queryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function replacePageQuery(params = {}) {
  const url = new URL(window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });
  window.history.replaceState({}, "", url);
}

function absoluteSiteUrl(path = "/") {
  return new URL(path, window.location.origin).toString();
}

function upsertMetaTag(selector, attributes) {
  let node = document.head.querySelector(selector);
  if (!node) {
    node = document.createElement("meta");
    Object.entries(attributes).forEach(([key, value]) => {
      if (key !== "content") {
        node.setAttribute(key, value);
      }
    });
    document.head.appendChild(node);
  }
  if (Object.prototype.hasOwnProperty.call(attributes, "content")) {
    node.setAttribute("content", attributes.content || "");
  }
  return node;
}

function upsertLinkTag(selector, attributes) {
  let node = document.head.querySelector(selector);
  if (!node) {
    node = document.createElement("link");
    Object.entries(attributes).forEach(([key, value]) => {
      if (key !== "href") {
        node.setAttribute(key, value);
      }
    });
    document.head.appendChild(node);
  }
  if (Object.prototype.hasOwnProperty.call(attributes, "href")) {
    node.setAttribute("href", attributes.href || "");
  }
  return node;
}

function setPageMetadata(options = {}) {
  const title = String(options.title || "OmniForum");
  const description = String(options.description || "OmniForum is a modern community forum for discussion, support, and direct messaging.");
  const canonicalPath = options.canonicalPath || `${window.location.pathname}${window.location.search}`;
  const canonicalUrl = absoluteSiteUrl(canonicalPath);
  const ogType = options.type || "website";
  const robots = options.noindex ? "noindex, nofollow" : "index, follow";
  document.title = title;
  upsertMetaTag('meta[name="description"]', { name: "description", content: description });
  upsertMetaTag('meta[property="og:site_name"]', { property: "og:site_name", content: "OmniForum" });
  upsertMetaTag('meta[property="og:title"]', { property: "og:title", content: title });
  upsertMetaTag('meta[property="og:description"]', { property: "og:description", content: description });
  upsertMetaTag('meta[property="og:type"]', { property: "og:type", content: ogType });
  upsertMetaTag('meta[property="og:url"]', { property: "og:url", content: canonicalUrl });
  upsertMetaTag('meta[name="twitter:card"]', { name: "twitter:card", content: options.imageUrl ? "summary_large_image" : "summary" });
  upsertMetaTag('meta[name="twitter:title"]', { name: "twitter:title", content: title });
  upsertMetaTag('meta[name="twitter:description"]', { name: "twitter:description", content: description });
  upsertMetaTag('meta[name="robots"]', { name: "robots", content: robots });
  if (options.imageUrl) {
    const imageUrl = absoluteSiteUrl(options.imageUrl);
    upsertMetaTag('meta[property="og:image"]', { property: "og:image", content: imageUrl });
    upsertMetaTag('meta[name="twitter:image"]', { name: "twitter:image", content: imageUrl });
  } else {
    document.head.querySelector('meta[property="og:image"]')?.remove();
    document.head.querySelector('meta[name="twitter:image"]')?.remove();
  }
  upsertLinkTag('link[rel="canonical"]', { rel: "canonical", href: canonicalUrl });
}

function paginationLabel(pagination) {
  if (!pagination) return "";
  const total = Number(pagination.totalItems || 0);
  const offset = Number(pagination.offset || 0);
  if (!total) return "0 results";
  const start = offset + 1;
  const end = Math.min(total, offset + Number(pagination.pageSize || 0));
  return `${start}-${end} of ${total}`;
}

function renderPaginationControls(pagination, handlers = {}) {
  if (!pagination || Number(pagination.totalPages || 1) <= 1) return "";
  const page = Number(pagination.page || 1);
  const totalPages = Number(pagination.totalPages || 1);
  const previousAction = handlers.previous || "";
  const nextAction = handlers.next || "";
  return `
    <div class="pagination-bar">
      <div class="pagination-copy">Page ${page} of ${totalPages} · ${escapeHtml(paginationLabel(pagination))}</div>
      <div class="pagination-actions">
        <button class="btn btn-ghost btn-sm" ${pagination.hasPrev ? `onclick="${previousAction}"` : "disabled"}>Previous</button>
        <button class="btn btn-ghost btn-sm" ${pagination.hasNext ? `onclick="${nextAction}"` : "disabled"}>Next</button>
      </div>
    </div>
  `;
}
