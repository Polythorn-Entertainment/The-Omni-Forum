document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

async function refreshCurrentPage() {
  try {
    await Auth.refresh();
  } catch {
    Auth.setCurrentUser(null);
  }
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();
  hydrateContactForm();
  setPageMetadata({
    title: "OmniForum — Contact",
    description: "Send a support, moderation, or account help request to OmniForum staff, with optional Discord contact details.",
    canonicalPath: `${window.location.pathname}${window.location.search || ""}`,
    type: "website",
  });
}

function hydrateContactForm() {
  const user = Auth.getCurrentUser();
  const name = document.getElementById("contactName");
  if (user && name && !name.value) {
    name.value = user.username;
  }
}

async function submitContactForm() {
  const error = document.getElementById("contactError");
  const success = document.getElementById("contactSuccess");
  const payload = {
    name: document.getElementById("contactName")?.value?.trim() || "",
    discordUsername: document.getElementById("contactDiscord")?.value?.trim() || "",
    subject: document.getElementById("contactSubject")?.value?.trim() || "",
    message: document.getElementById("contactMessage")?.value?.trim() || "",
  };

  if (error) error.classList.remove("visible");
  if (success) success.classList.remove("visible");

  try {
    await API.submitContact(payload);
    document.getElementById("contactForm")?.reset();
    hydrateContactForm();
    if (success) {
      success.textContent = "Message sent. Moderators and admins have been notified to review it.";
      success.classList.add("visible");
    }
    toast("Contact message sent.", "success");
    renderNavActions();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not send your message.";
      error.classList.add("visible");
    }
  }
}

window.refreshCurrentPage = refreshCurrentPage;
window.submitContactForm = submitContactForm;
