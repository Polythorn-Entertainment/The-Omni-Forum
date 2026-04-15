let leaderboardMetric = "xp";
let leaderboardMembers = [];
let leaderboardPodium = [];
let currentRank = null;
let leaderboardPagination = null;
let leaderboardPage = 1;

document.addEventListener("DOMContentLoaded", () => {
  refreshCurrentPage();
});

async function refreshCurrentPage() {
  renderNavActions();
  renderSidebarUser();
  renderFooterYear();

  leaderboardMetric = queryParam("metric") || "xp";
  leaderboardPage = Math.max(1, Number(queryParam("page") || 1));

  try {
    const data = await API.getLeaderboard(leaderboardMetric, {
      page: leaderboardPage,
      pageSize: 18,
    });
    leaderboardMetric = data.metric || leaderboardMetric;
    leaderboardMembers = data.members || [];
    leaderboardPodium = data.podium || [];
    currentRank = data.rank ?? null;
    leaderboardPagination = data.pagination || null;
    leaderboardPage = Number(leaderboardPagination?.page || leaderboardPage);
    renderNavActions();
    renderSidebarUser();
    renderLeaderboard();
    renderYourRank();
    document.querySelectorAll(".sort-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.metric === leaderboardMetric);
    });
  } catch (err) {
    const list = document.getElementById("leaderboardList");
    const podium = document.getElementById("podium");
    if (podium) podium.innerHTML = "";
    if (list) list.innerHTML = renderEmptyState("⚠️", "Could not load the leaderboard.", err.message || "Please try again.");
  }
}

function syncLeaderboardQuery() {
  replacePageQuery({
    metric: leaderboardMetric !== "xp" ? leaderboardMetric : "",
    page: leaderboardPage > 1 ? leaderboardPage : "",
  });
}

function setMetric(metric, button) {
  leaderboardMetric = metric;
  leaderboardPage = 1;
  document.querySelectorAll(".sort-tab").forEach((tab) => tab.classList.remove("active"));
  button?.classList.add("active");
  syncLeaderboardQuery();
  refreshCurrentPage();
}

function goToLeaderboardPage(page) {
  leaderboardPage = Math.max(1, Number(page || 1));
  syncLeaderboardQuery();
  refreshCurrentPage();
}

function metricLabel(member) {
  if (leaderboardMetric === "posts") return `${fmtNum(member.posts || 0)} posts`;
  if (leaderboardMetric === "role") return `${escapeHtml(DB.roles[member.role]?.label || member.role)}`;
  return `${fmtNum(member.xp || 0)} XP`;
}

function renderLeaderboard() {
  const podium = document.getElementById("podium");
  const list = document.getElementById("leaderboardList");
  if (!podium || !list) return;

  if (!leaderboardPodium.length && !leaderboardMembers.length) {
    podium.innerHTML = "";
    list.innerHTML = renderEmptyState("🏆", "No rankings yet.", "Start posting to light up the board.");
    return;
  }

  const podiumOrder = [1, 0, 2];
  const podiumHeights = ["100px", "130px", "80px"];
  const podiumColors = ["#c0c0c0", "#ffd166", "#cd7f32"];
  const podiumLabels = ["2nd", "1st", "3rd"];

  podium.innerHTML = podiumOrder
    .map((memberIndex, visualIndex) => {
      const member = leaderboardPodium[memberIndex];
      if (!member) return "";
      return `
        <div class="podium-card" onclick="showProfile(${JSON.stringify(member.id)})">
          ${makeAvatar(member, "podium")}
          <div class="podium-name">${escapeHtml(member.username)}</div>
          <div class="podium-score" style="color:${podiumColors[visualIndex]}">${metricLabel(member)}</div>
          <div class="podium-step" style="height:${podiumHeights[visualIndex]};background:${podiumColors[visualIndex]}20;border-color:${podiumColors[visualIndex]}40">
            ${podiumLabels[visualIndex]}
          </div>
        </div>
      `;
    })
    .join("");

  list.innerHTML = `
    ${leaderboardMembers.map((member, index) => {
      const rank = Number(leaderboardPagination?.offset || 0) + index + 4;
      return `
        <div class="leaderboard-item rank-other" onclick="showProfile(${JSON.stringify(member.id)})" style="cursor:pointer">
          <div class="rank-badge">${rank}</div>
          ${makeAvatar(member, "sm")}
          <div>
            <div class="leaderboard-name">${escapeHtml(member.username)}</div>
            <div class="leaderboard-meta">${roleBadge(member.role)}</div>
          </div>
          <div class="leaderboard-score">
            <div class="score-val">${metricLabel(member)}</div>
            <div class="score-label">${escapeHtml(leaderboardMetric.toUpperCase())}</div>
          </div>
        </div>
      `;
    }).join("")}
    ${renderPaginationControls(leaderboardPagination, {
      previous: "goToLeaderboardPage(leaderboardPage - 1)",
      next: "goToLeaderboardPage(leaderboardPage + 1)",
    })}
  `;
}

function renderYourRank() {
  const container = document.getElementById("yourRank");
  if (!container) return;
  const user = Auth.getCurrentUser();
  if (!user) {
    container.innerHTML = '<p class="muted-copy">Log in to see your rank.</p>';
    return;
  }

  const metricMember = [...leaderboardPodium, ...leaderboardMembers].find((member) => member.id === user.id) || user;
  container.innerHTML = `
    <div class="your-rank-num">#${currentRank || "—"}</div>
    <div class="tiny-copy">Your current rank</div>
    <div class="your-rank-metric">${metricLabel(metricMember)}</div>
  `;
}

window.refreshCurrentPage = refreshCurrentPage;
window.setMetric = setMetric;
window.goToLeaderboardPage = goToLeaderboardPage;
