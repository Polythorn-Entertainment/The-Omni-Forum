function modalError(message) {
  return `<div class="form-error visible">${escapeHtml(message)}</div>`;
}

function showLoginModal() {
  const resetSwitch = DB.canRequestEmailPasswordReset()
    ? '<div class="form-switch"><a onclick="showEmailResetRequestModal()">Forgot password?</a></div>'
    : "";
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Log In</div>
    <div class="form-error" id="loginError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="loginUsername" type="text" placeholder="Your username" autocomplete="username">
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-input" id="loginPassword" type="password" placeholder="Your password" autocomplete="current-password">
    </div>
    <div class="form-group">
      <label class="form-label">Recovery Code</label>
      <input class="form-input" id="loginRecoveryCode" type="text" placeholder="Optional one-time code if you forgot your password" autocomplete="one-time-code">
      <div class="form-hint">Use this instead of a password only if you previously generated recovery codes.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doLogin()">Log In</button>
    </div>
    ${resetSwitch}
    <div class="form-switch">Need an account? <a onclick="showRegisterModal()">Create one</a></div>
  `);

  window.setTimeout(() => document.getElementById("loginUsername")?.focus(), 50);
  document.getElementById("loginPassword")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") doLogin();
  });
}

function showRegisterModal() {
  const emailField = DB.isEmailAuthEnabled()
    ? `
      <div class="form-group">
        <label class="form-label">Email</label>
        <input class="form-input" id="regEmail" type="email" placeholder="Optional recovery email" autocomplete="email">
        <div class="form-hint">Only used for opt-in email recovery on forums where email auth is enabled.</div>
      </div>
    `
    : "";
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Create Account</div>
    <div class="form-error" id="regError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="regUsername" type="text" placeholder="Choose a username" maxlength="24">
      <div class="form-hint">Letters, numbers, underscores, and hyphens only.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-input" id="regPassword" type="password" placeholder="Choose a password" minlength="8">
      <div class="form-hint">Use at least 8 characters.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Confirm Password</label>
      <input class="form-input" id="regConfirm" type="password" placeholder="Confirm your password">
    </div>
    ${emailField}
    <div class="form-group">
      <label class="form-label">Invite Code</label>
      <input class="form-input" id="regInviteCode" type="text" placeholder="Optional unless the forum is invite-only" autocomplete="off">
      <div class="form-hint">If staff gave you an invite, enter it here. Some communities also require admin approval.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="doRegister()">Create Account</button>
    </div>
    <div class="form-switch">Already registered? <a onclick="showLoginModal()">Log in</a></div>
  `);

  window.setTimeout(() => document.getElementById("regUsername")?.focus(), 50);
}

function showEmailResetRequestModal() {
  if (!DB.canRequestEmailPasswordReset()) {
    toast("Email password reset is not enabled on this forum.", "info");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Reset Password</div>
    <div class="muted-copy">Enter your username or recovery email. If the account has email recovery configured, a reset link will be sent.</div>
    <div class="form-error" id="emailResetError"></div>
    <div class="form-group">
      <label class="form-label">Username or Email</label>
      <input class="form-input" id="emailResetIdentifier" type="text" placeholder="username or email@example.com" autocomplete="username">
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="showLoginModal()">Back</button>
      <button class="btn btn-primary" onclick="requestEmailPasswordReset()">Send Reset Link</button>
    </div>
  `);
  window.setTimeout(() => document.getElementById("emailResetIdentifier")?.focus(), 50);
}

function showEmailResetCompleteModal(token) {
  if (!DB.canRequestEmailPasswordReset()) {
    toast("Email password reset is not enabled on this forum.", "info");
    return;
  }
  openModal(`
    <div class="modal-title">Choose New Password</div>
    <div class="muted-copy">Set a new password for the account linked to this reset email.</div>
    <div class="form-error" id="emailResetCompleteError"></div>
    <input id="emailResetToken" type="hidden" value="${escapeHtml(token)}">
    <div class="form-group">
      <label class="form-label">New Password</label>
      <input class="form-input" id="emailResetNewPassword" type="password" placeholder="Use at least 8 characters" autocomplete="new-password">
    </div>
    <div class="form-group">
      <label class="form-label">Confirm Password</label>
      <input class="form-input" id="emailResetConfirmPassword" type="password" placeholder="Confirm the new password" autocomplete="new-password">
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="completeEmailPasswordReset()">Update Password</button>
    </div>
  `, { dismissible: false });
  window.setTimeout(() => document.getElementById("emailResetNewPassword")?.focus(), 50);
}

function showForcedPasswordResetModal() {
  const user = Auth.getCurrentUser();
  if (!user?.mustResetPassword) return;
  openModal(`
    <div class="modal-title">Reset Your Password</div>
    <div class="muted-copy">A temporary recovery password was used on this account. Set a new password to continue.</div>
    <div class="form-error" id="passwordResetError"></div>
    <div class="form-group">
      <label class="form-label">New Password</label>
      <input class="form-input" id="passwordResetNew" type="password" placeholder="Choose a new password" autocomplete="new-password">
      <div class="form-hint">Use at least 8 characters. This replaces the temporary recovery password.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Confirm Password</label>
      <input class="form-input" id="passwordResetConfirm" type="password" placeholder="Confirm the new password" autocomplete="new-password">
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="logoutUser()">Log Out</button>
      <button class="btn btn-primary" onclick="saveForcedPasswordReset()">Update Password</button>
    </div>
  `, { size: "lg", dismissible: false });

  window.setTimeout(() => document.getElementById("passwordResetNew")?.focus(), 50);
  document.getElementById("passwordResetConfirm")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") saveForcedPasswordReset();
  });
}

function handleAuthStateChanged(user) {
  closeNavMenu();
  applyViewerPresentationPreferences(user);
  renderNavActions();
  renderSidebarUser();
  startLiveUpdates();
  if (user?.mustResetPassword) {
    window.setTimeout(() => {
      if (Auth.mustResetPassword()) {
        showForcedPasswordResetModal();
      }
    }, 0);
    return;
  }
}

async function doLogin() {
  const error = document.getElementById("loginError");
  const username = document.getElementById("loginUsername")?.value?.trim();
  const password = document.getElementById("loginPassword")?.value || "";
  const recoveryCode = document.getElementById("loginRecoveryCode")?.value?.trim() || "";
  if (error) error.classList.remove("visible");

  try {
    const user = await Auth.login(username, password, recoveryCode);
    closeModal(null, true);
    toast(user.mustResetPassword ? `Welcome back, ${user.username}. Please set a new password.` : `Welcome back, ${user.username}.`, "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Login failed.";
      error.classList.add("visible");
    }
  }
}

async function doRegister() {
  const error = document.getElementById("regError");
  const username = document.getElementById("regUsername")?.value?.trim();
  const password = document.getElementById("regPassword")?.value || "";
  const confirm = document.getElementById("regConfirm")?.value || "";
  const inviteCode = document.getElementById("regInviteCode")?.value?.trim() || "";
  const email = DB.isEmailAuthEnabled() ? (document.getElementById("regEmail")?.value?.trim() || "") : "";
  if (error) error.classList.remove("visible");

  if (password !== confirm) {
    if (error) {
      error.textContent = "Passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }

  try {
    const data = await Auth.register(username, password, inviteCode, email);
    closeModal();
    if (data.pendingApproval) {
      toast(data.message || "Account created and pending admin approval.", "success", 5200);
      await refreshApp();
      return;
    }
    const user = data.currentUser;
    toast(`Welcome to OmniForum, ${user.username}.`, "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Registration failed.";
      error.classList.add("visible");
    }
  }
}

async function requestEmailPasswordReset() {
  const error = document.getElementById("emailResetError");
  const identifier = document.getElementById("emailResetIdentifier")?.value?.trim() || "";
  if (error) error.classList.remove("visible");
  try {
    const data = await API.requestEmailPasswordReset({ identifier });
    closeModal();
    toast(data.message || "If that account has email recovery enabled, a reset link has been sent.", "success", 5200);
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not request a reset link.";
      error.classList.add("visible");
    }
  }
}

async function completeEmailPasswordReset() {
  const error = document.getElementById("emailResetCompleteError");
  const token = document.getElementById("emailResetToken")?.value || "";
  const newPassword = document.getElementById("emailResetNewPassword")?.value || "";
  const confirm = document.getElementById("emailResetConfirmPassword")?.value || "";
  if (error) error.classList.remove("visible");
  if (newPassword !== confirm) {
    if (error) {
      error.textContent = "Passwords do not match.";
      error.classList.add("visible");
    }
    return;
  }
  try {
    const data = await API.completeEmailPasswordReset({ token, newPassword });
    closeModal(null, true);
    toast(data.message || "Password updated. You can now log in.", "success", 5200);
    showLoginModal();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not update the password.";
      error.classList.add("visible");
    }
  }
}

async function maybeOpenEmailResetFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("emailResetToken") || "";
  if (!token) return;
  try {
    await API.getAuthFeatures();
    if (DB.canRequestEmailPasswordReset()) {
      params.delete("emailResetToken");
      const cleanQuery = params.toString();
      const nextUrl = `${window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}${window.location.hash || ""}`;
      window.history.replaceState({}, "", nextUrl);
      showEmailResetCompleteModal(token);
    }
  } catch {
    // Ignore capability lookup failures; the normal page error handling will still work.
  }
}

async function logoutUser() {
  try {
    await Auth.logout();
    closeModal(null, true);
    toast("Logged out.", "info");
    await refreshApp();
  } catch (err) {
    toast(err.message || "Could not log out.", "error");
  }
}

async function refreshApp() {
  renderNavActions();
  renderSidebarUser();
  if (typeof window.refreshCurrentPage === "function") {
    await window.refreshCurrentPage();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.setTimeout(maybeOpenEmailResetFromUrl, 0);
});
