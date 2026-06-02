/* Local draft persistence helpers */

function draftStorageKey(scope, id = "") {
  return `nexus:draft:${scope}:${id || "default"}`;
}

function loadDraft(scope, id = "") {
  try {
    const raw = window.localStorage.getItem(draftStorageKey(scope, id));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveDraft(scope, id = "", payload = {}) {
  try {
    window.localStorage.setItem(draftStorageKey(scope, id), JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures.
  }
}

function clearDraft(scope, id = "") {
  try {
    window.localStorage.removeItem(draftStorageKey(scope, id));
  } catch {
    // Ignore localStorage failures.
  }
}

function listDrafts() {
  const prefix = "nexus:draft:";
  const drafts = [];
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key || !key.startsWith(prefix)) continue;
      const [, , scope, ...idParts] = key.split(":");
      const raw = window.localStorage.getItem(key);
      const payload = raw ? JSON.parse(raw) : {};
      const title = payload.title || payload.content || "";
      drafts.push({
        key,
        scope,
        id: idParts.join(":") || "default",
        savedAt: payload.savedAt || "",
        title: String(title || "Untitled draft").slice(0, 80),
        payload,
      });
    }
  } catch {
    return drafts;
  }
  return drafts.sort((a, b) => String(b.savedAt || "").localeCompare(String(a.savedAt || "")));
}

function serializeJsArg(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return `'${String(value ?? "")
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'")
    .replaceAll("\r", "\\r")
    .replaceAll("\n", "\\n")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029")}'`;
}
