function renderSidebarUser() {
  const container = document.getElementById("sidebarUser");
  if (!container) return;
  const user = Auth.getCurrentUser();

  if (!user) {
    container.innerHTML = `
      <div class="sidebar-login-prompt">
        <p>Join the forum to post, like replies, and unlock member spaces.</p>
        <div class="sidebar-login-buttons">
          <button class="btn btn-primary" onclick="showLoginModal()">Log In</button>
          <button class="btn btn-ghost" onclick="showRegisterModal()">Create Account</button>
        </div>
      </div>
    `;
    return;
  }

  const xpData = DB.getXPForNextLevel(user.xp);
  const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
  container.innerHTML = `
    <div class="user-avatar-row">
      ${makeAvatar(user)}
      <div class="user-meta">
        <div class="user-name">${escapeHtml(user.username)}</div>
        ${roleBadge(user.role)}
        ${user.statusText ? `<div class="tiny-copy">${escapeHtml(user.statusText)}</div>` : ""}
      </div>
    </div>
    <div class="user-stats-grid">
      <div class="user-stat-box">
        <div class="user-stat-val">${fmtNum(user.posts || 0)}</div>
        <div class="user-stat-label">Posts</div>
      </div>
      <div class="user-stat-box">
        <div class="user-stat-val">${fmtNum(user.xp || 0)}</div>
        <div class="user-stat-label">XP</div>
      </div>
    </div>
    <div class="xp-bar-wrap">
      <div class="xp-label">
        <span>${escapeHtml(xpData.label)} Progress</span>
        <span>${progress}%</span>
      </div>
      <progress class="xp-progress" value="${progress}" max="100"></progress>
    </div>
    <div class="stack-actions">
      <button class="btn btn-outline btn-sm" onclick="showProfile(${JSON.stringify(user.id)})">View Profile</button>
      <button class="btn btn-ghost btn-sm" onclick="goToSettingsPage()">Settings</button>
    </div>
  `;
}

function renderSidebarStats(stats) {
  const container = document.getElementById("sidebarStats");
  if (!container || !stats) return;
  container.innerHTML = `
    <li><span>Total Posts</span><strong>${fmtNum(stats.posts || 0)}</strong></li>
    <li><span>Total Threads</span><strong>${fmtNum(stats.threads || 0)}</strong></li>
    <li><span>Total Members</span><strong>${fmtNum(stats.members || 0)}</strong></li>
    <li><span>Online Now</span><strong>${fmtNum(stats.online || 0)}</strong></li>
  `;
}

function renderActivityFeed(activity = []) {
  const container = document.getElementById("activityList");
  if (!container) return;
  if (!activity.length) {
    container.innerHTML = `<li class="activity-item"><span class="activity-text">No activity yet. Start the first conversation.</span></li>`;
    return;
  }

  container.innerHTML = activity
    .map((item) => {
      const target = item.target ? ` <strong>${escapeHtml(item.target)}</strong>` : "";
      return `
        <li class="activity-item">
          <span class="activity-dot"></span>
          <span class="activity-text">
            <strong>${escapeHtml(item.user)}</strong> ${escapeHtml(item.action)}${target}
            <span class="activity-time">${escapeHtml(formatRelativeTime(item.createdAt))}</span>
          </span>
        </li>
      `;
    })
    .join("");
}

function renderTopMembers(members = []) {
  const container = document.getElementById("topMembers");
  if (!container) return;
  if (!members.length) {
    container.innerHTML = `<li class="top-member empty-top-member">No members yet.</li>`;
    return;
  }

  container.innerHTML = members
    .map((user, index) => `
      <li class="top-member clickable" onclick="showProfile(${JSON.stringify(user.id)})">
        <span class="rank-num">${index + 1}</span>
        ${makeAvatar(user, "xs")}
        <div class="member-info">
          <div class="member-name">${escapeHtml(user.username)}</div>
          <div class="member-posts">${user.statusText ? escapeHtml(user.statusText) : `${fmtNum(user.posts || 0)} posts`}</div>
        </div>
        ${roleBadge(user.role)}
      </li>
    `)
    .join("");
}

function renderHeroStats(stats) {
  const posts = document.getElementById("statPosts");
  const members = document.getElementById("statMembers");
  const online = document.getElementById("statOnline");
  if (posts) posts.textContent = fmtNum(stats?.posts || 0);
  if (members) members.textContent = fmtNum(stats?.members || 0);
  if (online) online.textContent = fmtNum(stats?.online || 0);
}

function renderTicker(items = []) {
  const container = document.getElementById("tickerWrap");
  if (!container) return;
  const source = items.length ? [...items, ...items] : ["OmniForum is ready for its first real members."];
  const inner = source
    .map((item) => `<span class="ticker-item"><span class="ticker-dot"></span>${escapeHtml(item)}</span>`)
    .join("");
  container.innerHTML = `<div class="ticker-inner">${inner}</div>`;
}

function renderFooterYear() {
  const year = document.getElementById("footerYear");
  if (year) year.textContent = String(new Date().getFullYear());
}
