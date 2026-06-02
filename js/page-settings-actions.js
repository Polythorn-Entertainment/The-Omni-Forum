/* Settings save, recovery, sessions, relationships, and export actions */

async function saveSettingsProfile() {
  const error = document.getElementById("settingsProfileError");
  const username = document.getElementById("settingsUsername")?.value?.trim() || "";
  const bio = document.getElementById("settingsBio")?.value || "";
  const statusText = document.getElementById("settingsStatusText")?.value?.trim() || "";
  const email = DB.isEmailAuthEnabled() ? (document.getElementById("settingsEmail")?.value?.trim() || "") : "";
  const profileBadge = document.getElementById("settingsProfileBadge")?.value?.trim() || "";
  const profileAccent = document.getElementById("settingsProfileAccent")?.value || "";
  const signature = document.getElementById("settingsSignature")?.value || "";
  const recoveryDiscordUsername = document.getElementById("settingsRecoveryDiscord")?.value?.trim() || "";
  const avatarInput = document.getElementById("settingsAvatarInput");
  const removeAvatar = Boolean(document.getElementById("settingsRemoveAvatar")?.checked);
  if (error) error.classList.remove("visible");

  try {
    const avatarUpload = await readSingleImageUpload(avatarInput?.files, {
      maxBytes: UPLOAD_LIMITS.avatarBytes,
      field: "Profile picture",
    });
    const payload = { username, bio, statusText, profileBadge, profileAccent, signature, recoveryDiscordUsername };
    if (DB.isEmailAuthEnabled()) {
      payload.email = email;
    }
    if (avatarUpload) {
      payload.avatarUpload = avatarUpload;
    } else if (removeAvatar) {
      payload.removeAvatar = true;
    }
    const data = await API.updateProfile(payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Profile updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your profile settings.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsPreferences() {
  const error = document.getElementById("settingsPreferencesError");
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({
      dmPrivacy: document.getElementById("settingsDmPrivacy")?.value || "everyone",
      notifyReplies: Boolean(document.getElementById("settingsNotifyReplies")?.checked),
      notifyLikes: Boolean(document.getElementById("settingsNotifyLikes")?.checked),
      notifyMentions: Boolean(document.getElementById("settingsNotifyMentions")?.checked),
      notifyDms: Boolean(document.getElementById("settingsNotifyDms")?.checked),
      blurSensitiveMedia: Boolean(document.getElementById("settingsBlurSensitiveMedia")?.checked),
      compactPostLayout: Boolean(document.getElementById("settingsCompactPostLayout")?.checked),
      hideIgnoredContent: Boolean(document.getElementById("settingsHideIgnoredContent")?.checked),
    });
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Preferences updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your communication preferences.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsTheme() {
  const error = document.getElementById("settingsThemeError");
  const selected = document.querySelector("input[name='settingsSiteTheme']:checked")?.value || "midnight";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({ siteTheme: selected });
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Theme updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your theme.";
      error.classList.add("visible");
    }
  }
}

async function saveSettingsPassword() {
  const error = document.getElementById("settingsPasswordError");
  const currentPassword = document.getElementById("settingsCurrentPassword")?.value || "";
  const newPassword = document.getElementById("settingsNewPassword")?.value || "";
  const confirmPassword = document.getElementById("settingsConfirmPassword")?.value || "";
  if (error) error.classList.remove("visible");

  if (newPassword !== confirmPassword) {
    if (error) {
      error.textContent = "New passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const payload = { newPassword };
    if (!Auth.mustResetPassword()) {
      payload.currentPassword = currentPassword;
    }
    const data = await API.updatePassword(payload);
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Password updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update your password.";
      error.classList.add("visible");
    }
  }
}

async function showRecoveryCodesModal() {
  if (!Auth.getCurrentUser()) {
    toast("Log in to manage recovery codes.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Recovery Codes</div>
    <div class="muted-copy">Loading recovery status...</div>
  `, { size: "lg" });
  try {
    const data = await API.getRecoveryCodes();
    const summary = data.summary || {};
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Recovery Codes</div>
      <div class="muted-copy">Recovery codes are one-time login keys for email-free account recovery. Using one starts a forced password reset session.</div>
      <div class="detail-list mt-16">
        <div><span>Active Codes</span><strong>${fmtNum(summary.active || 0)}</strong></div>
        <div><span>Total Created</span><strong>${fmtNum(summary.total || 0)}</strong></div>
        <div><span>Discord Verification</span><strong>${escapeHtml(data.discordUsername ? `@${data.discordUsername}` : "Not set")}</strong></div>
      </div>
      <div class="form-error" id="recoveryCodesError"></div>
      ${Auth.mustResetPassword() ? "" : `
        <div class="form-group mt-16">
          <label class="form-label">Current Password</label>
          <input class="form-input" id="recoveryCodesPassword" type="password" autocomplete="current-password" placeholder="Required to regenerate codes">
        </div>
      `}
      <div class="form-actions">
        <button class="btn btn-primary" onclick="generateRecoveryCodes()">Generate New Codes</button>
        <button class="btn btn-ghost" onclick="closeModal()">Close</button>
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load recovery codes.", "error");
  }
}

async function generateRecoveryCodes() {
  const error = document.getElementById("recoveryCodesError");
  if (error) error.classList.remove("visible");
  try {
    const data = await API.createRecoveryCodes({
      currentPassword: document.getElementById("recoveryCodesPassword")?.value || "",
    });
    const codes = data.codes || [];
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Save These Codes</div>
      <div class="form-success visible">These codes are shown once. Store them somewhere safe before closing this window.</div>
      <pre class="forum-code-block admin-log-block"><code>${escapeHtml(codes.join("\n"))}</code></pre>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="copyTextValue(${serializeJsArg(codes.join("\n"))}, 'Recovery codes')">Copy Codes</button>
        <button class="btn btn-primary" onclick="closeModal(); refreshCurrentPage()">Done</button>
      </div>
    `, { size: "lg" });
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not generate recovery codes.";
      error.classList.add("visible");
    } else {
      toast(err.message || "Could not generate recovery codes.", "error");
    }
  }
}

async function revokeSettingsSessions() {
  const error = document.getElementById("settingsSessionsError");
  if (error) error.classList.remove("visible");

  try {
    const data = await API.revokeOtherSessions();
    Auth.setCurrentUser(data.currentUser || null);
    toast(data.message || "Other sessions signed out.", "success");
    await refreshCurrentPage();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not revoke your other sessions.";
      error.classList.add("visible");
    }
  }
}

async function updateSettingsRelationship(userId, payload) {
  try {
    const data = await API.updateUserRelationship(userId, payload);
    if (data.currentUser) {
      Auth.setCurrentUser(data.currentUser);
    }
    toast(data.message || "Member controls updated.", "success");
    await refreshCurrentPage();
  } catch (err) {
    toast(err.message || "Could not update that member relationship.", "error");
  }
}

async function exportSettingsData() {
  try {
    const data = await API.exportMyData();
    downloadJsonFile(data.filename || "omniforum-export.json", data.export || {});
    toast("Account export downloaded.", "success");
  } catch (err) {
    toast(err.message || "Could not export your account data.", "error");
  }
}
