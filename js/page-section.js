/* Section page compatibility exports. */

window.refreshCurrentPage = refreshCurrentPage;
window.sortThreads = sortThreads;
window.filterThreads = filterThreads;
window.goToSectionPage = goToSectionPage;
window.showNewThreadModal = showNewThreadModal;
window.submitNewThread = submitNewThread;
window.getLiveContext = () => ({
  section: currentSection?.id || queryParam("section") || "",
});
window.handleLiveSnapshot = (snapshot) => {
  const section = snapshot?.section;
  if (!section || !currentSection || section.id !== currentSection.id) return;
  if (
    Number(section.threadCount || 0) !== Number(currentSection.threads || 0)
    || String(section.lastThreadAt || "") !== String(currentSection.lastThread?.updatedAt || "")
  ) {
    scheduleSectionLiveRefresh();
  }
};
window.clearNewThreadDraftAndForm = clearNewThreadDraftAndForm;
window.removeNewThreadUpload = removeNewThreadUpload;
window.updateNewThreadUploadAlt = updateNewThreadUploadAlt;
window.insertComposerToken = window.insertComposerToken || insertComposerToken;
