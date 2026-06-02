/* Upload, inline media, forum markup, and paste/drop helpers */

function splitLines(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .trim()
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function humanFileSize(bytes) {
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(mb >= 10 ? 0 : 1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

function buildAltFromFilename(name) {
  return String(name || "Forum image")
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .trim()
    .slice(0, 120) || "Forum image";
}

function isSupportedImageFile(file) {
  return SUPPORTED_IMAGE_TYPES.has(file?.type) || SUPPORTED_IMAGE_NAME.test(file?.name || "");
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file?.name || "that file"}.`));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(file);
  });
}

async function readImageUploads(files, options = {}) {
  const items = Array.from(files || []).filter(Boolean);
  const maxFiles = options.maxFiles ?? UPLOAD_LIMITS.postCount;
  const maxBytes = options.maxBytes ?? UPLOAD_LIMITS.postBytes;
  const field = options.field || "Images";
  if (!items.length) return [];
  if (items.length > maxFiles) {
    if (maxFiles <= 0) {
      throw new Error(`Remove an existing image before adding more ${field.toLowerCase()}.`);
    }
    throw new Error(`${field} supports up to ${maxFiles} file${maxFiles === 1 ? "" : "s"} at once.`);
  }

  return Promise.all(items.map(async (file) => {
    if (!isSupportedImageFile(file)) {
      throw new Error(`Only PNG, JPG, GIF, and WEBP files are supported for ${field.toLowerCase()}.`);
    }
    if ((file.size || 0) > maxBytes) {
      throw new Error(`${file.name} is too large. Keep each file under ${humanFileSize(maxBytes)}.`);
    }
    return {
      name: file.name,
      alt: buildAltFromFilename(file.name),
      dataUrl: await readFileAsDataUrl(file),
    };
  }));
}

async function readSingleImageUpload(files, options = {}) {
  const uploads = await readImageUploads(files, { ...options, maxFiles: 1 });
  return uploads[0] || null;
}

function renderInlineMedia(media = [], options = {}) {
  const items = Array.isArray(media) ? media.filter((item) => item?.url) : [];
  if (!items.length) return "";
  const sensitive = Boolean(options.sensitive);
  const blurMedia = Boolean(options.blurMedia);
  return `
    <div class="inline-media-grid${items.length === 1 ? " single" : ""}${sensitive ? " sensitive" : ""}${blurMedia ? " sensitive-blur" : ""}">
      ${items.map((item) => `
        <figure class="inline-media-card-wrap${sensitive && blurMedia ? " sensitive-media-card blurred" : ""}">
          <a class="inline-media-card" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
            <img src="${escapeHtml(item.thumbnailUrl || item.url)}" alt="${escapeHtml(item.alt || "Forum image")}" loading="lazy">
          </a>
          ${sensitive && blurMedia ? '<button class="sensitive-media-toggle" type="button" onclick="toggleSensitiveMedia(event)">Reveal media</button>' : ""}
          ${item.alt ? `<figcaption class="inline-media-caption">${escapeHtml(item.alt)}</figcaption>` : ""}
        </figure>
      `).join("")}
    </div>
  `;
}

function preprocessForumMarkup(text) {
  return String(text || "")
    .replace(/\[quote=([^\]]+)\]([\s\S]*?)\[\/quote\]/gi, (_, author, body) => {
      return `> ${String(author || "").trim()} wrote:\n> ${String(body || "").trim().replace(/\n/g, "\n> ")}`;
    })
    .replace(/\[quote\]([\s\S]*?)\[\/quote\]/gi, (_, body) => `> ${String(body || "").trim().replace(/\n/g, "\n> ")}`)
    .replace(/\[code\]([\s\S]*?)\[\/code\]/gi, (_, body) => `\n\`\`\`\n${String(body || "").trim()}\n\`\`\`\n`)
    .replace(/\[b\]([\s\S]*?)\[\/b\]/gi, "**$1**")
    .replace(/\[i\]([\s\S]*?)\[\/i\]/gi, "*$1*")
    .replace(/\[u\]([\s\S]*?)\[\/u\]/gi, "<u>$1</u>")
    .replace(/\[s\]([\s\S]*?)\[\/s\]/gi, "~~$1~~")
    .replace(/\[spoiler\]([\s\S]*?)\[\/spoiler\]/gi, '<span class="forum-spoiler">$1</span>')
    .replace(/\[url=([^\]]+)\]([\s\S]*?)\[\/url\]/gi, "[$2]($1)");
}

function applyInlineFormatting(raw) {
  let text = escapeHtml(raw || "");
  text = text.replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/gi, '<span class="forum-underline">$1</span>');
  text = text.replace(/&lt;span class=&quot;forum-spoiler&quot;&gt;([\s\S]*?)&lt;\/span&gt;/gi, '<span class="forum-spoiler">$1</span>');
  text = text.replace(/`([^`]+?)`/g, '<code class="inline-code">$1</code>');
  text = text.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__([^_]+?)__/g, "<strong>$1</strong>");
  text = text.replace(/(^|[^\*])\*([^*\n]+?)\*(?!\*)/g, "$1<em>$2</em>");
  text = text.replace(/(^|[^_])_([^_\n]+?)_(?!_)/g, "$1<em>$2</em>");
  text = text.replace(/~~([^~]+?)~~/g, "<s>$1</s>");
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  text = text.replace(/(^|[\s(])((https?:\/\/|www\.)[^\s<]+)/gi, (_, prefix, match) => {
    const href = match.startsWith("http") ? match : `https://${match}`;
    return `${prefix}<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(match)}</a>`;
  });
  text = text.replace(/(^|[^\w-])@([A-Za-z0-9_-]{3,24})/g, '$1<span class="mention-token">@$2</span>');
  return text;
}

function renderMarkupBlocks(text) {
  const normalized = preprocessForumMarkup(text)
    .replace(/\r\n/g, "\n")
    .trim();
  if (!normalized) return "";
  const blocks = normalized.split(/\n{2,}/).filter(Boolean);
  return blocks.map((block) => {
    const lines = block.split("\n");
    if (block.startsWith("```") && block.endsWith("```")) {
      const code = block.replace(/^```/, "").replace(/```$/, "").trim();
      return `<pre class="forum-code-block"><code>${escapeHtml(code)}</code></pre>`;
    }
    if (lines.every((line) => line.trim().startsWith(">"))) {
      const quoteLines = lines.map((line) => line.replace(/^\s*>\s?/, ""));
      return `<blockquote class="forum-quote">${quoteLines.map((line) => applyInlineFormatting(line)).join("<br>")}</blockquote>`;
    }
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return `<ul class="forum-list">${lines.map((line) => `<li>${applyInlineFormatting(line.replace(/^\s*[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    }
    const headingMatch = lines[0].match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = Math.min(3, headingMatch[1].length + 1);
      const remaining = lines.slice(1).join("\n");
      return `
        <div class="forum-heading-block">
          <h${level} class="forum-heading level-${level}">${applyInlineFormatting(headingMatch[2])}</h${level}>
          ${remaining ? `<div class="forum-heading-copy">${applyInlineFormatting(remaining)}</div>` : ""}
        </div>
      `;
    }
    return `<p>${applyInlineFormatting(block).replace(/\n/g, "<br>")}</p>`;
  }).join("");
}

function renderUserContent(text, media = [], options = {}) {
  const copy = renderMarkupBlocks(text);
  const mediaMarkup = renderInlineMedia(media, options);
  if (!copy && !mediaMarkup) {
    return "<p></p>";
  }
  return `${copy}${mediaMarkup}`;
}

function bindDropTarget(dropTarget, fileInput, onFiles) {
  if (!dropTarget || !fileInput) return () => {};
  const prevent = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };
  const onDrop = (event) => {
    prevent(event);
    dropTarget.classList.remove("drag-active");
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) {
      fileInput.files = event.dataTransfer.files;
      if (typeof onFiles === "function") onFiles(files);
    }
  };
  ["dragenter", "dragover"].forEach((name) => dropTarget.addEventListener(name, (event) => {
    prevent(event);
    dropTarget.classList.add("drag-active");
  }));
  ["dragleave", "dragend"].forEach((name) => dropTarget.addEventListener(name, (event) => {
    prevent(event);
    dropTarget.classList.remove("drag-active");
  }));
  dropTarget.addEventListener("drop", onDrop);
  const onKeydown = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    fileInput.click();
  };
  dropTarget.addEventListener("keydown", onKeydown);
  return () => {
    dropTarget.removeEventListener("drop", onDrop);
    dropTarget.removeEventListener("keydown", onKeydown);
  };
}

async function readPastedImageUploads(items, options = {}) {
  const files = Array.from(items || [])
    .map((item) => item?.getAsFile?.())
    .filter((file) => file && isSupportedImageFile(file));
  if (!files.length) return [];
  return readImageUploads(files, options);
}

function bindPasteImageTarget(target, onUploads, options = {}) {
  if (!target || typeof onUploads !== "function") return () => {};
  const handler = async (event) => {
    try {
      const uploads = await readPastedImageUploads(event.clipboardData?.items, options);
      if (!uploads.length) return;
      event.preventDefault();
      await onUploads(uploads, { fromPaste: true });
    } catch (err) {
      if (typeof window.toast === "function") {
        window.toast(err.message || "Could not add the pasted image.", "error");
      }
    }
  };
  target.addEventListener("paste", handler);
  return () => target.removeEventListener("paste", handler);
}

function toggleSensitiveMedia(event) {
  const card = event?.target?.closest(".sensitive-media-card");
  if (!card) return;
  card.classList.toggle("blurred");
  const toggle = card.querySelector(".sensitive-media-toggle");
  if (toggle) {
    toggle.textContent = card.classList.contains("blurred") ? "Reveal media" : "Hide media";
  }
}

function downloadJsonFile(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "omniforum-export.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadTextFile(filename, content, contentType = "text/plain") {
  const blob = new Blob([String(content || "")], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "omniforum-export.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderUploadPreviewList(uploads = [], options = {}) {
  const removeAction = options.removeAction || "";
  const altAction = options.altAction || "";
  if (!uploads.length) {
    return `<div class="upload-preview-empty">Drop images here or use the file picker.</div>`;
  }
  return `
    <div class="upload-preview-grid">
      ${uploads.map((item, index) => `
        <div class="upload-preview-card">
          <div class="upload-preview-image-wrap">
            <img class="upload-preview-image" src="${escapeHtml(item.dataUrl || item.url || "")}" alt="${escapeHtml(item.alt || "Upload preview")}">
            ${removeAction ? `<button class="upload-preview-remove" type="button" onclick="${removeAction}(${index})" aria-label="Remove upload">✕</button>` : ""}
          </div>
          <div class="upload-preview-meta">${escapeHtml(item.name || `Image ${index + 1}`)}</div>
          <label class="sr-only" for="upload-alt-${index}">Image description ${index + 1}</label>
          <input
            class="form-input upload-preview-alt"
            id="upload-alt-${index}"
            type="text"
            maxlength="120"
            value="${escapeHtml(item.alt || "")}"
            placeholder="Short alt text / description"
            ${altAction ? `oninput="${altAction}(${index}, this.value)"` : ""}
          >
        </div>
      `).join("")}
    </div>
  `;
}
