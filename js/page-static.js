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
}

window.refreshCurrentPage = refreshCurrentPage;
