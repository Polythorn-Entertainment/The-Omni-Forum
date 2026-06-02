async function refreshCurrentPage() {
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();

  const sectionId = queryParam("section");
  currentSort = queryParam("sort") || "latest";
  currentSearch = queryParam("q") || "";
  currentPage = Math.max(1, Number(queryParam("page") || 1));

  if (!sectionId) {
    renderSectionError("⚠️", "Section not found.", "Choose a section from the homepage.");
    return;
  }

  try {
    const data = await API.getSection(sectionId, {
      q: currentSearch,
      sort: currentSort,
      page: currentPage,
      pageSize: 20,
    });
    currentSection = data.section;
    currentThreads = data.threads || [];
    currentTopMembers = data.topMembers || [];
    currentPagination = data.pagination || null;
    currentPage = Number(currentPagination?.page || currentPage);

    renderNavActions();
    renderSidebarUser();

    document.title = `OmniForum — ${currentSection.name}`;
    document.getElementById("breadSection").textContent = currentSection.name;
    const searchInput = document.getElementById("threadSearch");
    if (searchInput) searchInput.value = currentSearch;
    document.querySelectorAll(".sort-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.sort === currentSort);
    });

    renderSectionHeader();
    renderSectionStats();
    renderTopMembers(currentTopMembers);
    renderThreads(currentThreads);
    setPageMetadata({
      title: `OmniForum — ${currentSection.name}`,
      description: currentSection.desc || `${fmtNum(currentSection.threads || 0)} threads in ${currentSection.name} on OmniForum.`,
      canonicalPath: `/pages/section.html?section=${encodeURIComponent(currentSection.id)}`,
      type: "website",
    });
  } catch (err) {
    if (err.status === 403) {
      renderSectionError("🔒", "This section is restricted.", err.message || "You do not have permission to view it.");
    } else {
      renderSectionError("⚠️", "Could not load this section.", err.message || "Please try again.");
    }
    setPageMetadata({
      title: "OmniForum — Section",
      description: "Browse section threads and ongoing discussions on OmniForum.",
      canonicalPath: `/pages/section.html${sectionId ? `?section=${encodeURIComponent(sectionId)}` : ""}`,
      type: "website",
    });
  }
}

function scheduleSectionLiveRefresh() {
  if (sectionLiveRefreshTimer) return;
  sectionLiveRefreshTimer = window.setTimeout(async () => {
    sectionLiveRefreshTimer = null;
    await refreshCurrentPage();
  }, 900);
}

function renderSectionError(icon, title, detail) {
  const list = document.getElementById("threadList");
  if (list) list.innerHTML = renderEmptyState(icon, title, detail);
  document.getElementById("sectionHeader").innerHTML = "";
  document.getElementById("sectionStats").innerHTML = "";
  renderTopMembers([]);
}
