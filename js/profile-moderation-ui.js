function moderationActionLabel(type) {
  return {
    warn: "Warning",
    note: "Staff Note",
    timeout: "Timeout",
    clear_timeout: "Timeout Cleared",
    mute: "Mute",
    clear_mute: "Mute Cleared",
    shadow_mute: "Shadow Mute",
    clear_shadow_mute: "Shadow Mute Cleared",
    ban: "Ban",
    unban: "Unban",
    xp_adjust: "XP Adjustment",
    temp_password: "Temporary Password Set",
    role_change: "Role Change",
  }[type] || "Moderation";
}

function renderModerationStatus(moderation) {
  if (!moderation) return "";
  const items = [];
  if (moderation.isBanned) {
    items.push(`
      <div class="moderation-status-card danger">
        <div class="moderation-status-title">Account Banned</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.banReason || "No ban reason recorded.")}</div>
        <div class="tiny-copy">
          ${moderation.bannedAt ? `Issued ${escapeHtml(formatDateTime(moderation.bannedAt))}` : ""}
          ${moderation.bannedBy?.username ? ` by ${escapeHtml(moderation.bannedBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isTimedOut) {
    items.push(`
      <div class="moderation-status-card warn">
        <div class="moderation-status-title">Timed Out</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.timeoutReason || "Posting access is currently restricted.")}</div>
        <div class="tiny-copy">
          Until ${escapeHtml(formatDateTime(moderation.timeoutUntil))}
          ${moderation.timeoutBy?.username ? ` · set by ${escapeHtml(moderation.timeoutBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isMuted) {
    items.push(`
      <div class="moderation-status-card warn">
        <div class="moderation-status-title">Muted</div>
        <div class="moderation-status-copy">${escapeHtml(moderation.muteReason || "Posting and direct messaging are temporarily disabled.")}</div>
        <div class="tiny-copy">
          Until ${escapeHtml(formatDateTime(moderation.muteUntil))}
          ${moderation.muteBy?.username ? ` · set by ${escapeHtml(moderation.muteBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (moderation.isShadowMuted) {
    items.push(`
      <div class="moderation-status-card info">
        <div class="moderation-status-title">Shadow Muted</div>
        <div class="moderation-status-copy">Staff has enabled a quiet moderation state on this account.</div>
      </div>
    `);
  }
  if (moderation.passwordResetRequired) {
    items.push(`
      <div class="moderation-status-card info">
        <div class="moderation-status-title">Password Reset Required</div>
        <div class="moderation-status-copy">A temporary recovery password is active for this account. The user must choose a new password after their next login.</div>
        <div class="tiny-copy">
          ${moderation.passwordResetSetAt ? `Issued ${escapeHtml(formatDateTime(moderation.passwordResetSetAt))}` : ""}
          ${moderation.passwordResetExpiresAt ? ` · expires ${escapeHtml(formatDateTime(moderation.passwordResetExpiresAt))}` : ""}
          ${moderation.passwordResetBy?.username ? ` by ${escapeHtml(moderation.passwordResetBy.username)}` : ""}
        </div>
      </div>
    `);
  }
  if (!items.length) {
    items.push(`
      <div class="moderation-status-card ok">
        <div class="moderation-status-title">Account Clear</div>
        <div class="moderation-status-copy">No active timeouts, bans, or mutes on this account.</div>
      </div>
    `);
  }
  return `<div class="moderation-status-stack">${items.join("")}</div>`;
}

function renderModerationHistory(history = []) {
  if (!history.length) {
    return `<div class="centered-message">No moderation history on this account yet.</div>`;
  }
  return history
    .map((item) => {
      const delta = Number(item.deltaXp || 0);
      const xpLine = item.type === "xp_adjust"
        ? `<div class="moderation-history-impact">${delta > 0 ? "+" : ""}${escapeHtml(delta)} XP</div>`
        : "";
      const expiresLine = item.expiresAt
        ? `<div class="tiny-copy">Until ${escapeHtml(formatDateTime(item.expiresAt))}</div>`
        : "";
      const content = item.note || item.reason || "No extra details recorded.";
      return `
        <div class="moderation-history-card">
          <div class="moderation-history-head">
            <div>
              <div class="moderation-history-title">${escapeHtml(moderationActionLabel(item.type))}</div>
              <div class="moderation-history-meta">
                <span>${escapeHtml(item.actor?.username || "Staff")}</span>
                <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
              </div>
            </div>
            ${xpLine}
          </div>
          <div class="moderation-history-copy">${escapeHtml(content)}</div>
          ${expiresLine}
        </div>
      `;
    })
    .join("");
}

function renderSessionAuditList(items = []) {
  if (!items.length) {
    return `<div class="centered-message">No recent session activity is available for this account yet.</div>`;
  }
  return items.map((item) => `
    <div class="moderation-history-card">
      <div class="moderation-history-head">
        <div>
          <div class="moderation-history-title">${escapeHtml(item.userAgent || "Unknown browser")}</div>
          <div class="moderation-history-meta">
            <span>${escapeHtml(item.active ? "Active session" : "Expired session")}</span>
            <span>${escapeHtml(formatDateTime(item.lastSeenAt || item.createdAt))}</span>
          </div>
        </div>
      </div>
      <div class="detail-list notice-detail-list">
        <div><span>IP</span><strong>${escapeHtml(item.lastSeenIp || item.ip || "Unknown")}</strong></div>
        <div><span>Started</span><strong>${escapeHtml(formatDateTime(item.createdAt))}</strong></div>
        <div><span>Expires</span><strong>${escapeHtml(formatDateTime(item.expiresAt))}</strong></div>
      </div>
    </div>
  `).join("");
}

function renderModerationActionOptions(user) {
  const moderation = user.moderation || {};
  const options = [
    { value: "warn", label: "Warn User" },
    { value: "note", label: "Staff Note" },
    { value: "timeout", label: moderation.isTimedOut ? "Update Timeout" : "Timeout User" },
    { value: "mute", label: moderation.isMuted ? "Update Mute" : "Mute User" },
    moderation.isMuted ? { value: "clear_mute", label: "Clear Mute" } : null,
    moderation.isShadowMuted ? { value: "clear_shadow_mute", label: "Clear Shadow Mute" } : { value: "shadow_mute", label: "Shadow Mute User" },
    { value: "xp_adjust", label: "Adjust XP" },
    user.canIssueTempPassword ? { value: "set_temp_password", label: "Set Temp Password" } : null,
    moderation.isTimedOut ? { value: "clear_timeout", label: "Clear Timeout" } : null,
    moderation.isBanned ? { value: "unban", label: "Unban User" } : { value: "ban", label: "Ban User" },
  ].filter(Boolean);
  return options
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

function moderationActionConfig(action) {
  const configs = {
    warn: {
      hint: "Logs a formal warning in the moderation timeline.",
      label: "Warning Reason",
      placeholder: "Explain what rule or behavior triggered this warning.",
      button: "Log Warning",
      showDuration: false,
      showXp: false,
    },
    note: {
      hint: "Internal note for moderators and admins only.",
      label: "Staff Note",
      placeholder: "Add investigation context, follow-up reminders, or staff-only notes.",
      button: "Save Note",
      showDuration: false,
      showXp: false,
    },
    timeout: {
      hint: "Temporarily removes the account's ability to post, edit, delete, or react.",
      label: "Timeout Reason",
      placeholder: "Explain why the account is being timed out.",
      button: "Apply Timeout",
      showDuration: true,
      showXp: false,
    },
    mute: {
      hint: "Temporarily blocks posting and direct messages without applying a full timeout.",
      label: "Mute Reason",
      placeholder: "Explain why the account is being muted.",
      button: "Apply Mute",
      showDuration: true,
      showXp: false,
    },
    clear_timeout: {
      hint: "Restores the user's posting access immediately.",
      label: "Optional Note",
      placeholder: "Optional note about why the timeout was lifted.",
      button: "Clear Timeout",
      showDuration: false,
      showXp: false,
    },
    clear_mute: {
      hint: "Restores the user's posting and messaging access.",
      label: "Optional Note",
      placeholder: "Optional note about why the mute was lifted.",
      button: "Clear Mute",
      showDuration: false,
      showXp: false,
    },
    shadow_mute: {
      hint: "New threads and replies from this account stay hidden from regular readers.",
      label: "Shadow Mute Reason",
      placeholder: "Document why this account is entering silent moderation.",
      button: "Apply Shadow Mute",
      showDuration: false,
      showXp: false,
    },
    clear_shadow_mute: {
      hint: "Stops hiding new content from this account.",
      label: "Optional Note",
      placeholder: "Optional note about why silent moderation was lifted.",
      button: "Clear Shadow Mute",
      showDuration: false,
      showXp: false,
    },
    ban: {
      hint: "Revokes active sessions and blocks the account from logging back in.",
      label: "Ban Reason",
      placeholder: "Explain why this account is being banned.",
      button: "Ban User",
      showDuration: false,
      showXp: false,
    },
    unban: {
      hint: "Restores the user's ability to sign in again.",
      label: "Optional Note",
      placeholder: "Optional note about why the ban was lifted.",
      button: "Lift Ban",
      showDuration: false,
      showXp: false,
    },
    xp_adjust: {
      hint: "Grant or remove XP with an audit trail entry.",
      label: "Reason",
      placeholder: "Explain why XP is being changed.",
      button: "Update XP",
      showDuration: false,
      showXp: true,
      showTempPassword: false,
    },
    set_temp_password: {
      hint: "Replaces the account password, signs out active sessions, and forces the user to set a new password after login.",
      label: "Recovery Note (Optional)",
      placeholder: "Optional internal note about this recovery request.",
      button: "Set Temporary Password",
      showDuration: false,
      showXp: false,
      showTempPassword: true,
    },
  };
  return configs[action] || configs.warn;
}

function updateModerationActionForm() {
  const action = document.getElementById("moderationAction")?.value || "warn";
  const config = moderationActionConfig(action);
  const hint = document.getElementById("moderationActionHint");
  const label = document.getElementById("moderationReasonLabel");
  const reason = document.getElementById("moderationReason");
  const durationGroup = document.getElementById("moderationDurationGroup");
  const xpGroup = document.getElementById("moderationXpGroup");
  const tempPasswordGroup = document.getElementById("moderationTempPasswordGroup");
  const tempPasswordConfirmGroup = document.getElementById("moderationTempPasswordConfirmGroup");
  const tempPasswordExpiryGroup = document.getElementById("moderationTempPasswordExpiryGroup");
  const button = document.getElementById("moderationSubmitButton");

  if (hint) hint.textContent = config.hint;
  if (label) label.textContent = config.label;
  if (reason) reason.placeholder = config.placeholder;
  if (durationGroup) durationGroup.classList.toggle("is-hidden", !config.showDuration);
  if (xpGroup) xpGroup.classList.toggle("is-hidden", !config.showXp);
  if (tempPasswordGroup) tempPasswordGroup.classList.toggle("is-hidden", !config.showTempPassword);
  if (tempPasswordConfirmGroup) tempPasswordConfirmGroup.classList.toggle("is-hidden", !config.showTempPassword);
  if (tempPasswordExpiryGroup) tempPasswordExpiryGroup.classList.toggle("is-hidden", !config.showTempPassword);
  if (button) button.textContent = config.button;
}

async function saveModerationAction(userId) {
  const error = document.getElementById("moderationError");
  if (error) error.classList.remove("visible");

  const action = document.getElementById("moderationAction")?.value || "warn";
  const reason = document.getElementById("moderationReason")?.value?.trim() || "";
  const duration = document.getElementById("moderationDuration")?.value || "";
  const deltaXp = document.getElementById("moderationXpDelta")?.value?.trim() || "";
  const tempPassword = document.getElementById("moderationTempPassword")?.value || "";
  const tempPasswordConfirm = document.getElementById("moderationTempPasswordConfirm")?.value || "";
  const tempPasswordExpires = document.getElementById("moderationTempPasswordExpires")?.value || "48";
  const payload = { action };

  if (action === "note") {
    payload.note = reason;
  } else if (action === "set_temp_password") {
    if (tempPassword !== tempPasswordConfirm) {
      if (error) {
        error.textContent = "Temporary passwords do not match.";
        error.classList.add("visible");
      }
      return;
    }
    payload.tempPassword = tempPassword;
    payload.expiresInHours = Number(tempPasswordExpires || 48);
    if (reason) payload.note = reason;
  } else if (reason) {
    payload.reason = reason;
  }
  if (action === "timeout" || action === "mute") {
    payload.minutes = Number(duration || 0);
  }
  if (action === "xp_adjust") {
    payload.deltaXp = Number(deltaXp || 0);
  }

  try {
    const data = await API.moderateUser(userId, payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Moderation updated.", "success");
    await showProfile(userId);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save that moderation action.";
      error.classList.add("visible");
    }
  }
}

async function saveForcedPasswordReset() {
  const error = document.getElementById("passwordResetError");
  const newPassword = document.getElementById("passwordResetNew")?.value || "";
  const confirm = document.getElementById("passwordResetConfirm")?.value || "";
  if (error) error.classList.remove("visible");

  if (newPassword !== confirm) {
    if (error) {
      error.textContent = "Passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const data = await API.updatePassword({ newPassword });
    Auth.setCurrentUser(data.currentUser || null);
    closeModal(null, true);
    toast(data.message || "Password updated.", "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update your password.";
      error.classList.add("visible");
    }
  }
}
