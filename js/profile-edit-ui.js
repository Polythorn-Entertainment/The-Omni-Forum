function showEditProfileModal() {
  const user = Auth.getCurrentUser();
  if (!user) {
    showLoginModal();
    return;
  }

  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Edit Profile</div>
    <div class="form-error" id="profileError"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-input" id="profileUsername" maxlength="24" value="${escapeHtml(user.username || "")}" placeholder="Username">
      <div class="form-hint">3-24 characters using letters, numbers, _ or -.</div>
    </div>
    <div class="form-group">
      <label class="form-label">Bio</label>
      <textarea class="form-textarea" id="profileBio" maxlength="280" placeholder="Tell the forum a little about yourself.">${escapeHtml(user.bio || "")}</textarea>
      <div class="form-hint">Up to 280 characters.</div>
    </div>
    <div class="form-actions">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" onclick="saveProfile()">Save Changes</button>
    </div>
  `, { size: "lg" });
}

async function saveProfile() {
  const error = document.getElementById("profileError");
  const username = document.getElementById("profileUsername")?.value || "";
  const bio = document.getElementById("profileBio")?.value || "";
  if (error) error.classList.remove("visible");

  try {
    const data = await API.updateProfile({ username, bio });
    Auth.setCurrentUser(data.currentUser || null);
    closeModal();
    toast(data.message || "Profile updated.", "success");
    await refreshApp();
  } catch (err) {
    if (error) {
      error.textContent = err.message || "Could not save your profile.";
      error.classList.add("visible");
    }
  }
}

async function saveUserRole(userId) {
  const select = document.getElementById("profileRoleSelect");
  if (!select) return;
  try {
    await API.updateUserRole(userId, select.value);
    toast("Role updated.", "success");
    await showProfile(userId);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    }
  } catch (err) {
    toast(err.message || "Could not update role.", "error");
  }
}

async function saveUserRelationship(userId, payload) {
  try {
    const data = await API.updateUserRelationship(userId, payload);
    if (data.currentUser) {
      Auth.setCurrentUser(data.currentUser);
    }
    toast(data.message || "Member controls updated.", "success");
    await showProfile(userId);
    if (typeof window.refreshCurrentPage === "function") {
      await window.refreshCurrentPage();
    }
  } catch (err) {
    toast(err.message || "Could not update member controls.", "error");
  }
}
