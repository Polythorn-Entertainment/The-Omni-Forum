/* Signup controls and invite review UI */

function renderSignupControls(controls = {}) {
  const settings = controls.settings || {};
  const pending = controls.pending || [];
  const invites = controls.invites || [];
  const pendingBody = pending.length
    ? pending.map((item) => `
      <div class="moderation-history-card">
        <div class="moderation-history-head">
          <div>
            <div class="moderation-history-title">${escapeHtml(item.username)}</div>
            <div class="moderation-history-meta">
              <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
              ${item.inviteCodeUsed ? `<span>Invite: ${escapeHtml(item.inviteCodeUsed)}</span>` : "<span>No invite</span>"}
              ${item.registrationIp ? `<span>IP: ${escapeHtml(item.registrationIp)}</span>` : ""}
            </div>
          </div>
          ${roleBadge(item.role || "new")}
        </div>
        <textarea class="form-textarea notice-note" id="registrationNote-${item.id}" maxlength="500" placeholder="Optional internal review note"></textarea>
        <div class="form-actions">
          <button class="btn btn-primary btn-sm" onclick="reviewSignup(${JSON.stringify(item.id)}, 'approve')">Approve</button>
          <button class="btn btn-danger btn-sm" onclick="reviewSignup(${JSON.stringify(item.id)}, 'reject')">Reject</button>
        </div>
      </div>
    `).join("")
    : renderEmptyState("✓", "No registrations are waiting for approval.");
  const inviteBody = invites.length
    ? invites.map((invite) => `
      <div class="moderation-history-card">
        <div class="moderation-history-head">
          <div>
            <div class="moderation-history-title">${escapeHtml(invite.code)}</div>
            <div class="moderation-history-meta">
              <span>${invite.enabled ? "Enabled" : "Disabled"}</span>
              <span>${fmtNum(invite.uses || 0)} / ${fmtNum(invite.maxUses || 0)} used</span>
              ${invite.expiresAt ? `<span>${invite.expired ? "Expired" : "Expires"} ${escapeHtml(formatDateTime(invite.expiresAt))}</span>` : "<span>No expiry</span>"}
            </div>
          </div>
          <div class="stack-actions">
            <button class="btn btn-ghost btn-sm" onclick="copyTextValue(${serializeJsArg(invite.code)}, 'Invite code')">Copy</button>
            <button class="btn ${invite.enabled ? "btn-outline" : "btn-primary"} btn-sm" onclick="toggleInvite(${JSON.stringify(invite.id)}, ${invite.enabled ? "false" : "true"})">${invite.enabled ? "Disable" : "Enable"}</button>
          </div>
        </div>
        ${invite.note ? `<div class="moderation-history-copy">${escapeHtml(invite.note)}</div>` : ""}
        <div class="tiny-copy">Remaining uses: ${fmtNum(invite.remainingUses || 0)}${invite.createdBy?.username ? ` · Created by ${escapeHtml(invite.createdBy.username)}` : ""}</div>
      </div>
    `).join("")
    : renderEmptyState("◇", "No invite codes yet.", "Create one when you want invite-only registration.");

  return `
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Signup Controls</div>
    <div class="muted-copy">Admin-only registration controls for invite-only mode, approval review, throttling, and blocked username patterns.</div>
    <div class="settings-tool-grid mt-16">
      <div class="settings-tool-card">
        <div class="settings-tool-title">Mode</div>
        <div class="detail-list">
          <div><span>Current</span><strong>${escapeHtml(settings.mode || "Open")}</strong></div>
          <div><span>Pending</span><strong>${fmtNum(controls.pendingCount || 0)}</strong></div>
        </div>
      </div>
      <div class="settings-tool-card">
        <div class="settings-tool-title">Abuse Controls</div>
        <div class="detail-list">
          <div><span>Invite Gate</span><strong>${settings.inviteRequired ? "On" : "Off"}</strong></div>
          <div><span>Approval Queue</span><strong>${settings.approvalRequired ? "On" : "Off"}</strong></div>
          <div><span>Captcha</span><strong>${settings.captchaSupported ? "Enabled" : "Not configured"}</strong></div>
        </div>
      </div>
    </div>
    <div class="form-error" id="signupControlsError"></div>
    <div class="page-section-title mt-18">Registration Settings</div>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupPublic"${settings.publicRegistrationEnabled ? " checked" : ""}> <span>Allow public registration without closing the signup form entirely</span></label>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupInviteRequired"${settings.inviteRequired ? " checked" : ""}> <span>Require a valid invite code</span></label>
    <label class="checkbox-row settings-checkbox-row"><input type="checkbox" id="signupApprovalRequired"${settings.approvalRequired ? " checked" : ""}> <span>Require admin approval before new users can log in</span></label>
    <div class="form-group mt-14">
      <label class="form-label">Blocked Username Patterns</label>
      <textarea class="form-textarea" id="signupBlockedPatterns" maxlength="4000" placeholder="admin*\n*support*\nmoderator">${escapeHtml(settings.blockedUsernamePatterns || "")}</textarea>
      <div class="form-hint">One pattern per line. Use wildcards like <code>admin*</code>, or plain words to block usernames containing that word.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-primary" onclick="saveSignupSettings()">Save Signup Settings</button>
      <button class="btn btn-ghost" onclick="showAdminOpsModal()">Back to Operations</button>
    </div>
    <div class="page-section-title mt-18">Create Invite</div>
    <div class="settings-form-grid">
      <div class="form-group">
        <label class="form-label">Custom Code</label>
        <input class="form-input" id="inviteCode" maxlength="40" placeholder="Leave blank to generate">
      </div>
      <div class="form-group">
        <label class="form-label">Max Uses</label>
        <input class="form-input" id="inviteMaxUses" type="number" min="1" max="500" value="1">
      </div>
      <div class="form-group">
        <label class="form-label">Expires In Days</label>
        <input class="form-input" id="inviteExpiresInDays" type="number" min="1" max="365" placeholder="Optional">
      </div>
      <div class="form-group full">
        <label class="form-label">Staff Note</label>
        <input class="form-input" id="inviteNote" maxlength="160" placeholder="Who this invite is for">
      </div>
    </div>
    <div class="form-actions">
      <button class="btn btn-outline" onclick="createSignupInvite()">Create Invite Code</button>
    </div>
    <div class="page-section-title mt-18">Approval Queue</div>
    <div class="moderation-history-list">${pendingBody}</div>
    <div class="page-section-title mt-18">Invite Codes</div>
    <div class="moderation-history-list">${inviteBody}</div>
    <div class="tiny-copy mt-14">${escapeHtml(settings.captchaNote || "")}</div>
  `;
}

async function showSignupControls() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can manage signup controls.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Signup Controls</div>
    <div class="muted-copy">Loading registration controls...</div>
  `, { size: "xl" });
  try {
    const data = await API.getAdminRegistration();
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Signup Controls</div>
      ${modalError(err.message || "Could not load signup controls.")}
    `, { size: "lg" });
  }
}

async function saveSignupSettings() {
  const error = document.getElementById("signupControlsError");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.updateRegistrationSettings({
      publicRegistrationEnabled: Boolean(document.getElementById("signupPublic")?.checked),
      inviteRequired: Boolean(document.getElementById("signupInviteRequired")?.checked),
      approvalRequired: Boolean(document.getElementById("signupApprovalRequired")?.checked),
      blockedUsernamePatterns: document.getElementById("signupBlockedPatterns")?.value || "",
    });
    toast(data.message || "Signup settings saved.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save signup settings.";
      error.classList.add("visible");
    } else {
      toast(err.message || "Could not save signup settings.", "error");
    }
  }
}

async function createSignupInvite() {
  try {
    const data = await API.createInvite({
      code: document.getElementById("inviteCode")?.value?.trim() || "",
      maxUses: Number(document.getElementById("inviteMaxUses")?.value || 1),
      expiresInDays: document.getElementById("inviteExpiresInDays")?.value || "",
      note: document.getElementById("inviteNote")?.value?.trim() || "",
    });
    toast(data.message || "Invite created.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not create invite.", "error");
  }
}

async function toggleInvite(inviteId, enabled) {
  try {
    const data = await API.updateInvite(inviteId, { enabled });
    toast(data.message || "Invite updated.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not update invite.", "error");
  }
}

async function reviewSignup(userId, action) {
  const note = document.getElementById(`registrationNote-${userId}`)?.value || "";
  try {
    const data = await API.reviewRegistration(userId, { action, note });
    toast(data.message || "Registration reviewed.", "success");
    openModal(renderSignupControls(data.controls || {}), { size: "xl" });
  } catch (err) {
    toast(err.message || "Could not review that registration.", "error");
  }
}
