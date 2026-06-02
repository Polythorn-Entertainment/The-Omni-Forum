const modalState = {
  dismissible: true,
  lastFocus: null,
};

function modalFocusableElements(modal) {
  return Array.from(
    modal.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")
  ).filter((node) => !node.disabled && node.offsetParent !== null);
}

function handleModalKeydown(event) {
  const overlay = document.getElementById("modalOverlay");
  const modal = document.getElementById("modal");
  if (!overlay || !modal || overlay.classList.contains("hidden")) return;
  if (event.key === "Escape" && modalState.dismissible) {
    event.preventDefault();
    closeModal(null, true);
    return;
  }
  if (event.key !== "Tab") return;
  const focusable = modalFocusableElements(modal);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function openModal(html, options = {}) {
  const modal = document.getElementById("modal");
  const overlay = document.getElementById("modalOverlay");
  if (!modal || !overlay) return;
  modalState.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  modal.classList.remove("modal-lg");
  modal.classList.remove("modal-xl");
  if (options.size === "lg") modal.classList.add("modal-lg");
  if (options.size === "xl") modal.classList.add("modal-xl");
  modalState.dismissible = options.dismissible !== false;
  modal.innerHTML = html;
  modal.querySelectorAll(".modal-close").forEach((button) => {
    button.setAttribute("type", "button");
    button.setAttribute("aria-label", button.getAttribute("aria-label") || "Close dialog");
    button.setAttribute("title", button.getAttribute("title") || "Close dialog");
  });
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-label", modal.querySelector(".modal-title")?.textContent?.trim() || "Dialog");
  modal.setAttribute("tabindex", "-1");
  overlay.classList.remove("hidden");
  overlay.setAttribute("aria-hidden", "false");
  document.addEventListener("keydown", handleModalKeydown);
  window.setTimeout(() => {
    const focusTarget = modalFocusableElements(modal)[0] || modal;
    focusTarget.focus();
  }, 0);
}

function closeModal(event, force = false) {
  const overlay = document.getElementById("modalOverlay");
  if (!overlay) return;
  if (!modalState.dismissible && !force) return;
  if (!event || event.target === overlay) {
    modalState.dismissible = true;
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
    document.removeEventListener("keydown", handleModalKeydown);
    modalState.lastFocus?.focus?.();
    modalState.lastFocus = null;
  }
}

function installAccessibilityShell() {
  const root = document.getElementById("app") || document.body;
  if (!document.querySelector(".skip-link")) {
    const link = document.createElement("a");
    link.href = "#mainContent";
    link.className = "skip-link";
    link.textContent = "Skip to main content";
    document.body.insertBefore(link, document.body.firstChild);
  }
  const main = document.querySelector("main");
  if (main) {
    main.id = main.id || "mainContent";
    main.tabIndex = -1;
  }
  const toastContainer = document.getElementById("toastContainer");
  if (toastContainer) {
    toastContainer.setAttribute("aria-live", "polite");
    toastContainer.setAttribute("aria-atomic", "true");
  }
  const overlay = document.getElementById("modalOverlay");
  if (overlay) {
    overlay.setAttribute("aria-hidden", overlay.classList.contains("hidden") ? "true" : "false");
  }
  const modal = document.getElementById("modal");
  if (modal) {
    modal.setAttribute("tabindex", "-1");
  }
  root?.setAttribute?.("data-js-ready", "true");
}

window.openModal = openModal;
window.closeModal = closeModal;
window.installAccessibilityShell = installAccessibilityShell;
