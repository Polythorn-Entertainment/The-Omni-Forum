function currentLiveQuery() {
  if (typeof window.getLiveContext === "function") {
    const context = window.getLiveContext() || {};
    return {
      threadId: context.threadId || "",
      section: context.section || "",
    };
  }
  return {};
}

function closeLiveUpdates() {
  if (liveState.eventSource) {
    liveState.eventSource.close();
    liveState.eventSource = null;
  }
  if (liveState.reconnectTimer) {
    window.clearTimeout(liveState.reconnectTimer);
    liveState.reconnectTimer = null;
  }
}

function scheduleLiveReconnect() {
  closeLiveUpdates();
  liveState.reconnectTimer = window.setTimeout(() => {
    liveState.reconnectTimer = null;
    startLiveUpdates({ force: true });
  }, liveState.reconnectDelay);
  liveState.reconnectDelay = Math.min(liveState.reconnectDelay * 1.5, 12000);
}

function applyLiveSnapshot(snapshot = {}) {
  if (Object.prototype.hasOwnProperty.call(snapshot, "currentUser")) {
    Auth.setCurrentUser(snapshot.currentUser || null);
  } else {
    renderNavActions();
    renderSidebarUser();
  }
  if (typeof window.handleLiveSnapshot === "function") {
    window.handleLiveSnapshot(snapshot);
  }
}

function startLiveUpdates(options = {}) {
  if (!("EventSource" in window)) return;
  const query = currentLiveQuery();
  const key = JSON.stringify(query);
  if (!options.force && liveState.eventSource && liveState.key === key) {
    return;
  }
  closeLiveUpdates();
  liveState.key = key;
  liveState.reconnectDelay = 1500;
  const source = new EventSource(`/api/live/stream${buildQuery(query)}`);
  liveState.eventSource = source;
  source.addEventListener("snapshot", (event) => {
    try {
      const snapshot = JSON.parse(event.data || "{}");
      applyLiveSnapshot(snapshot);
    } catch {
      // Ignore malformed stream payloads and wait for the next frame.
    }
  });
  source.addEventListener("ping", () => {});
  source.onerror = () => {
    scheduleLiveReconnect();
  };
}

async function loadEnabledPlugins() {
  try {
    const data = await API.getPlugins();
    const plugins = data.plugins || [];
    plugins.forEach((plugin) => {
      (plugin.styles || []).forEach((href) => {
        if (pluginState.styles.has(href)) return;
        pluginState.styles.add(href);
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        link.dataset.pluginHref = href;
        document.head.appendChild(link);
      });
      (plugin.scripts || []).forEach((src) => {
        if (pluginState.scripts.has(src)) return;
        pluginState.scripts.add(src);
        const script = document.createElement("script");
        script.src = src;
        script.defer = true;
        script.dataset.pluginSrc = src;
        document.body.appendChild(script);
      });
    });
  } catch {
    // Plugin assets are optional; skip quietly if the endpoint is unavailable.
  }
}
