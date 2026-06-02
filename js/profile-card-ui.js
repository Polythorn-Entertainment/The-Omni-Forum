async function showProfile(userId) {
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Loading profile...</div>
  `);

  try {
    const data = await API.getUser(userId);
    const user = data.user;
    const viewer = Auth.getCurrentUser();
    const role = DB.roles[user.role] || DB.roles.new;
    const xpData = DB.getXPForNextLevel(user.xp || 0);
    const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
    const canManageRole = Boolean(user.canManageRole);
    const canModerate = Boolean(user.canModerate);
    const moderation = user.moderation || null;
    const showStaffHistory = !!viewer && Auth.isStaff();
    const sessionAudit = user.sessionAudit || [];
    const accentClass = profileAccentClass(user.profileAccent);

    const allowedRoles = Object.values(DB.roles)
      .filter((item) => {
        if (!canManageRole || !viewer) return false;
        if (viewer.role === "owner") return true;
        return item.level <= DB.getRoleLevel("mod");
      })
      .sort((left, right) => right.level - left.level);

    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="profile-header${accentClass ? ` ${accentClass}` : ""}">
        ${makeAvatar(user, "lg")}
        <div class="profile-username">${escapeHtml(user.username)}</div>
        ${user.profileBadge ? `<div class="profile-custom-badge${accentClass ? ` ${accentClass}` : ""}">${escapeHtml(user.profileBadge)}</div>` : ""}
        <div class="profile-role-row">${roleBadge(user.role)}</div>
        <div class="profile-joined">Member since ${escapeHtml(formatDate(user.joined))}${user.online ? ' · <span class="online-dot"></span> Online' : ""}</div>
        ${user.statusText ? `<div class="tiny-copy profile-status-copy">${escapeHtml(user.statusText)}</div>` : ""}
      </div>
      <div class="profile-bio">${user.bio ? `"${escapeHtml(user.bio)}"` : "No bio yet."}</div>
      ${user.signature ? `<div class="profile-signature">${renderUserContent(user.signature)}</div>` : ""}
      <div class="profile-stats-grid">
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.posts || 0)}</div>
          <div class="profile-stat-label">Posts</div>
        </div>
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.threads || 0)}</div>
          <div class="profile-stat-label">Threads</div>
        </div>
        <div class="profile-stat-box">
          <div class="profile-stat-val">${fmtNum(user.xp || 0)}</div>
          <div class="profile-stat-label">XP</div>
        </div>
      </div>
      <div class="xp-bar-wrap">
        <div class="xp-label">
          <span>${escapeHtml(xpData.label)} Progress</span>
          <span>${progress}%</span>
        </div>
        <progress class="xp-progress" value="${progress}" max="100"></progress>
      </div>
      <div class="detail-list">
        <div><span>Likes Received</span><strong>${fmtNum(user.likesReceived || 0)}</strong></div>
        <div><span>Status</span><strong>${user.online ? "Online" : "Offline"}</strong></div>
        ${moderation ? `<div><span>Restrictions</span><strong>${moderation.isBanned ? "Banned" : moderation.isTimedOut ? "Timed Out" : moderation.isMuted ? "Muted" : moderation.isShadowMuted ? "Shadow Muted" : moderation.passwordResetRequired ? "Reset Required" : "Clear"}</strong></div>` : ""}
      </div>
      ${moderation ? `
        <hr class="divider">
        <div class="page-section-title">Account Status</div>
        ${renderModerationStatus(moderation)}
      ` : ""}
      ${canManageRole ? `
        <hr class="divider">
        <div class="form-group">
          <label class="form-label">Manage Role</label>
          <select class="form-input" id="profileRoleSelect">
            ${allowedRoles
              .map((item) => `<option value="${escapeHtml(item.cssClass)}"${item.cssClass === user.role ? " selected" : ""}>${escapeHtml(item.label)}</option>`)
              .join("")}
          </select>
          <div class="form-hint">Owner can assign any role. Admin can assign up to mod.</div>
        </div>
      ` : ""}
      ${canModerate ? `
        <hr class="divider">
        <div class="page-section-title">Moderation Actions</div>
        <div class="form-error" id="moderationError"></div>
        <div class="moderation-panel">
          <div class="form-group">
            <label class="form-label">Action</label>
            <select class="form-input" id="moderationAction" onchange="updateModerationActionForm()">
              ${renderModerationActionOptions(user)}
            </select>
            <div class="form-hint" id="moderationActionHint"></div>
          </div>
          <div class="form-group" id="moderationDurationGroup">
            <label class="form-label">Duration</label>
            <select class="form-input" id="moderationDuration">
              <option value="60">1 hour</option>
              <option value="720">12 hours</option>
              <option value="1440" selected>1 day</option>
              <option value="4320">3 days</option>
              <option value="10080">7 days</option>
              <option value="43200">30 days</option>
            </select>
          </div>
          <div class="form-group" id="moderationXpGroup">
            <label class="form-label">XP Delta</label>
            <input class="form-input" id="moderationXpDelta" type="number" min="-5000" max="5000" step="1" value="25" placeholder="25 or -25">
            <div class="form-hint">Positive grants XP, negative removes it.</div>
          </div>
          <div class="form-group" id="moderationTempPasswordGroup">
            <label class="form-label">Temporary Password</label>
            <input class="form-input" id="moderationTempPassword" type="password" minlength="8" autocomplete="new-password" placeholder="Temporary recovery password">
            <div class="form-hint">Share this securely with the user. It is stored only as a password hash.</div>
          </div>
          <div class="form-group" id="moderationTempPasswordConfirmGroup">
            <label class="form-label">Confirm Temporary Password</label>
            <input class="form-input" id="moderationTempPasswordConfirm" type="password" minlength="8" autocomplete="new-password" placeholder="Confirm temporary password">
          </div>
          <div class="form-group" id="moderationTempPasswordExpiryGroup">
            <label class="form-label">Temporary Password Expires</label>
            <select class="form-input" id="moderationTempPasswordExpires">
              <option value="24">24 hours</option>
              <option value="48" selected>48 hours</option>
              <option value="72">72 hours</option>
              <option value="168">7 days</option>
            </select>
            <div class="form-hint">Expired temporary passwords cannot be used to log in.</div>
          </div>
          <div class="form-group">
            <label class="form-label" id="moderationReasonLabel">Reason</label>
            <textarea class="form-textarea moderation-textarea" id="moderationReason"></textarea>
          </div>
        </div>
      ` : ""}
      ${showStaffHistory ? `
        <hr class="divider">
        <div class="page-section-title">Moderation History</div>
        <div class="moderation-history-list">${renderModerationHistory(user.moderationHistory || [])}</div>
      ` : ""}
      ${(sessionAudit.length && (viewer?.id === user.id || Auth.isStaff())) ? `
        <hr class="divider">
        <div class="page-section-title">Recent Sessions</div>
        <div class="moderation-history-list">${renderSessionAuditList(sessionAudit)}</div>
      ` : ""}
      <div class="form-actions">
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="showReportModal('user', ${JSON.stringify(user.id)}, ${serializeJsArg(user.username)})">Report</button>` : ""}
        ${user.canMessage ? `<button class="btn btn-outline" onclick="showComposeMessageModal(${JSON.stringify(user.id)}, ${serializeJsArg(user.username)})">Message</button>` : ""}
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="saveUserRelationship(${JSON.stringify(user.id)}, { ignoreContent: ${user.relationship?.ignoreContent ? "false" : "true"}, blockDm: ${user.relationship?.blockDm ? "true" : "false"} })">${user.relationship?.ignoreContent ? "Unignore" : "Ignore"} Content</button>` : ""}
        ${viewer && viewer.id !== user.id ? `<button class="btn btn-ghost" onclick="saveUserRelationship(${JSON.stringify(user.id)}, { ignoreContent: ${user.relationship?.ignoreContent ? "true" : "false"}, blockDm: ${user.relationship?.blockDm ? "false" : "true"} })">${user.relationship?.blockDm ? "Unblock" : "Block"} DMs</button>` : ""}
        ${viewer?.id === user.id && moderation && (moderation.isBanned || moderation.isTimedOut || moderation.isMuted) ? '<button class="btn btn-outline" onclick="showAppealsQueue(\'all\')">Appeals</button>' : ""}
        ${viewer?.id === user.id ? '<button class="btn btn-ghost" onclick="goToSettingsPage()">Settings</button>' : ""}
        ${canManageRole ? `<button class="btn btn-primary" onclick="saveUserRole(${JSON.stringify(user.id)})">Save Role</button>` : ""}
        ${canModerate ? `<button class="btn btn-danger" id="moderationSubmitButton" onclick="saveModerationAction(${JSON.stringify(user.id)})">Apply Action</button>` : ""}
      </div>
    `, { size: canManageRole || canModerate || showStaffHistory || sessionAudit.length ? "xl" : "lg" });
    if (canModerate) {
      updateModerationActionForm();
    }
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Profile Unavailable</div>
      ${modalError(err.message || "Could not load that profile.")}
    `);
  }
}
