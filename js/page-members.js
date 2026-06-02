let allMembers = [];
let currentRoleFilter = "all";
let currentMemberPage = 1;
let currentMemberPagination = null;

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

async function refreshCurrentPage() {
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();

  currentRoleFilter = queryParam("role") || "all";
  currentMemberPage = Math.max(1, Number(queryParam("page") || 1));
  const search = queryParam("q") || "";

  const searchInput = document.getElementById("memberSearch");
  if (searchInput) searchInput.value = search;

  try {
    const data = await API.getUsers({
      q: search,
      role: currentRoleFilter !== "all" ? currentRoleFilter : "",
      page: currentMemberPage,
      pageSize: 24,
    });
    allMembers = data.members || [];
    currentMemberPagination = data.pagination || null;
    currentMemberPage = Number(currentMemberPagination?.page || currentMemberPage);
    renderNavActions();
    renderSidebarUser();
    renderRoleBreakdown(data.counts || {});
    renderMembers(allMembers);
    const count = document.getElementById("memberCount");
    if (count) {
      count.textContent = `${currentMemberPagination?.totalItems || allMembers.length} members`;
    }
    document.querySelectorAll(".sort-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.role === currentRoleFilter);
    });
    setPageMetadata({
      title: "OmniForum — Members",
      description: `Browse ${fmtNum(currentMemberPagination?.totalItems || allMembers.length)} community members on OmniForum.`,
      canonicalPath: `/pages/members.html${window.location.search || ""}`,
      type: "website",
    });
  } catch (err) {
    const grid = document.getElementById("membersGrid");
    if (grid) {
      grid.innerHTML = renderEmptyState("⚠️", "Could not load members.", err.message || "Please try again.");
    }
    setPageMetadata({
      title: "OmniForum — Members",
      description: "Browse community member profiles and activity on OmniForum.",
      canonicalPath: `/pages/members.html${window.location.search || ""}`,
      type: "website",
    });
  }
}

function syncMemberQuery() {
  replacePageQuery({
    q: document.getElementById("memberSearch")?.value?.trim() || "",
    role: currentRoleFilter !== "all" ? currentRoleFilter : "",
    page: currentMemberPage > 1 ? currentMemberPage : "",
  });
}

function renderMembers(members) {
  const grid = document.getElementById("membersGrid");
  if (!grid) return;
  if (!members.length) {
    grid.innerHTML = `<div class="grid-span-all">${renderEmptyState("👤", "No members match those filters.")}</div>`;
    return;
  }

  grid.innerHTML = `
    ${members.map((member) => `
      <div class="member-card" onclick="showProfile(${JSON.stringify(member.id)})">
        ${makeAvatar(member, "card")}
        <div class="member-card-name">${escapeHtml(member.username)}</div>
        ${roleBadge(member.role)}
        <div class="member-card-stats">${fmtNum(member.posts || 0)} posts · ${fmtNum(member.threads || 0)} threads</div>
        ${member.statusText ? `<div class="tiny-copy member-card-status">${escapeHtml(member.statusText)}</div>` : ""}
        <div class="tiny-copy member-card-meta">
          Joined ${escapeHtml(formatDate(member.joined))}
          ${member.online ? '&nbsp; <span class="online-dot"></span>' : ""}
        </div>
      </div>
    `).join("")}
    <div class="grid-span-all">
      ${renderPaginationControls(currentMemberPagination, {
        previous: "goToMemberPage(currentMemberPage - 1)",
        next: "goToMemberPage(currentMemberPage + 1)",
      })}
    </div>
  `;
}

function filterMembers() {
  currentMemberPage = 1;
  syncMemberQuery();
  refreshCurrentPage();
}

function filterRole(role, button) {
  currentRoleFilter = role;
  currentMemberPage = 1;
  document.querySelectorAll(".sort-tab").forEach((tab) => tab.classList.remove("active"));
  button?.classList.add("active");
  syncMemberQuery();
  refreshCurrentPage();
}

function goToMemberPage(page) {
  currentMemberPage = Math.max(1, Number(page || 1));
  syncMemberQuery();
  refreshCurrentPage();
}

function renderRoleBreakdown(counts) {
  const list = document.getElementById("roleBreakdown");
  if (!list) return;
  list.innerHTML = Object.entries(DB.roles)
    .map(([key, role]) => `<li><span>${role.icon} ${escapeHtml(role.label)}</span><strong>${fmtNum(counts[key] || 0)}</strong></li>`)
    .join("");
}

window.refreshCurrentPage = refreshCurrentPage;
window.filterMembers = filterMembers;
window.filterRole = filterRole;
window.goToMemberPage = goToMemberPage;
