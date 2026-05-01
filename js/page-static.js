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
  const pageMeta = {
    "/pages/rules.html": {
      title: "OmniForum — Rules",
      description: "Read the community rules, moderation standards, and posting expectations for OmniForum.",
    },
    "/pages/privacy.html": {
      title: "OmniForum — Privacy",
      description: "Learn what OmniForum stores, what staff can review, and how account and forum data is handled.",
    },
  }[window.location.pathname] || {
    title: document.title || "OmniForum",
    description: "Read OmniForum community information and policy pages.",
  };
  setPageMetadata({
    ...pageMeta,
    canonicalPath: `${window.location.pathname}${window.location.search || ""}`,
    type: "website",
  });
}

window.refreshCurrentPage = refreshCurrentPage;
