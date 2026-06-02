class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null && item !== "") {
          query.append(key, item);
        }
      });
      return;
    }
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, value);
    }
  });
  return query.toString() ? `?${query.toString()}` : "";
}

const API = {
  async request(path, options = {}) {
    const config = {
      method: options.method || "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    };

    if (options.body !== undefined) {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(options.body);
    }

    if (!["GET", "HEAD", "OPTIONS"].includes(String(config.method).toUpperCase())) {
      const csrfToken = window.Auth?.getCurrentUser?.()?.csrfToken;
      if (csrfToken) {
        config.headers["X-CSRF-Token"] = csrfToken;
      }
    }

    const response = await fetch(path, config);
    const text = await response.text();
    let payload = {};

    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { error: "The server returned invalid JSON." };
      }
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "roles") && window.DB) {
      DB.setRoles(payload.roles);
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "authFeatures") && window.DB) {
      DB.setAuthFeatures(payload.authFeatures);
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "currentUser") && window.Auth) {
      if (payload.currentUser?.authFeatures && window.DB) {
        DB.setAuthFeatures(payload.currentUser.authFeatures);
      }
      Auth.setCurrentUser(payload.currentUser);
    }

    if (payload && typeof payload === "object" && Object.prototype.hasOwnProperty.call(payload, "site") && typeof window.applySiteConfig === "function") {
      window.applySiteConfig(payload.site);
    }

    if (!response.ok) {
      throw new ApiError(payload?.error || `Request failed with status ${response.status}.`, response.status, payload);
    }

    return payload;
  },
};
