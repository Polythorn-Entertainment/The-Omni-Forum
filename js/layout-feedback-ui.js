function toast(message, type = "info", duration = 3500) {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const icons = { success: "✓", error: "✕", info: "◈" };
  const node = document.createElement("div");
  node.className = `toast ${type}`;
  node.innerHTML = `<span>${icons[type] || "◈"}</span><span>${escapeHtml(message)}</span>`;
  container.appendChild(node);
  window.setTimeout(() => {
    node.classList.add("toast-exiting");
    window.setTimeout(() => node.remove(), 300);
  }, duration);
}

async function copyTextValue(value, label = "Value") {
  try {
    await navigator.clipboard.writeText(String(value || ""));
    toast(`${label} copied.`, "success");
  } catch {
    toast(`Could not copy that ${label.toLowerCase()}.`, "error");
  }
}

function applyViewerPresentationPreferences(user) {
  const root = document.documentElement;
  root.dataset.compactPosts = user?.preferences?.compactPostLayout ? "1" : "0";
  root.dataset.hideIgnoredContent = user?.preferences?.hideIgnoredContent === false ? "0" : "1";
  root.dataset.blurSensitiveMedia = user?.preferences?.blurSensitiveMedia === false ? "0" : "1";
}
