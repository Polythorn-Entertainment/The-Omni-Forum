let currentSection = null;
let currentThreads = [];
let currentTopMembers = [];
let currentPagination = null;
let currentSort = "latest";
let currentSearch = "";
let currentPage = 1;
let newThreadUploads = [];
let sectionLiveRefreshTimer = null;
let newThreadDraftSavedTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});
