const Auth = {
  currentUser: null,

  setCurrentUser(user) {
    this.currentUser = user || null;
    if (typeof window.applySiteTheme === "function") {
      if (this.currentUser?.preferences?.siteTheme) {
        window.applySiteTheme(this.currentUser.preferences.siteTheme, { storage: "set" });
      } else {
        window.applySiteTheme(window.getSiteDefaultTheme?.() || "midnight", { storage: "clear" });
      }
    }
    if (typeof window.handleAuthStateChanged === "function") {
      window.handleAuthStateChanged(this.currentUser);
    }
  },

  getCurrentUser() {
    return this.currentUser;
  },

  async refresh() {
    const data = await API.getMe();
    this.setCurrentUser(data.currentUser || null);
    return this.currentUser;
  },

  async login(username, password, recoveryCode = "") {
    const data = await API.login({ username, password, recoveryCode });
    this.setCurrentUser(data.currentUser || null);
    return data.currentUser;
  },

  async register(username, password, inviteCode = "", email = "") {
    const payload = { username, password, inviteCode };
    if (email && DB.isEmailAuthEnabled()) payload.email = email;
    const data = await API.register(payload);
    this.setCurrentUser(data.currentUser || null);
    return data;
  },

  async logout() {
    const data = await API.logout();
    this.setCurrentUser(data.currentUser || null);
    return true;
  },

  hasRole(requiredRole) {
    if (!requiredRole) return true;
    const viewerRole = this.currentUser?.role;
    if (!viewerRole) {
      return DB.getRoleLevel(requiredRole) <= DB.getRoleLevel("new");
    }
    return DB.getRoleLevel(viewerRole) >= DB.getRoleLevel(requiredRole);
  },

  canView(sectionOrRole) {
    const requiredRole = typeof sectionOrRole === "string" ? sectionOrRole : sectionOrRole?.requiredRole;
    return this.hasRole(requiredRole || "new");
  },

  canPost(section) {
    if (!this.currentUser) return false;
    return this.hasRole(section?.writeRole || "new");
  },

  isStaff() {
    return this.hasRole("mod");
  },

  isAdmin() {
    return this.hasRole("admin");
  },

  isOwner() {
    return this.currentUser?.role === "owner";
  },

  mustResetPassword() {
    return Boolean(this.currentUser?.mustResetPassword);
  },
};

window.Auth = Auth;
