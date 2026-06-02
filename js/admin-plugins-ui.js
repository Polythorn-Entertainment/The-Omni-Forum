/* Plugin manager and trash restore UI */

async function showPluginManager() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can manage plugins.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Plugin Manager</div>
    <div class="muted-copy">Loading installed plugins...</div>
  `, { size: "lg" });
  try {
    const data = await API.getPlugins({ includeAll: 1 });
    const plugins = data.plugins || [];
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Plugin Manager</div>
      <div class="muted-copy">Only enabled plugins with manifest-declared client assets can load into OmniForum. CSS/JS changes may need a refresh to fully unload.</div>
      <div class="moderation-history-list mt-18">
        ${plugins.length ? plugins.map((plugin) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(plugin.name)}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(plugin.id)}</span>
                  <span>v${escapeHtml(plugin.version || "0.0.0")}</span>
                  <span>${plugin.enabled ? "Enabled" : "Disabled"}</span>
                </div>
              </div>
              <button class="btn ${plugin.enabled ? "btn-outline" : "btn-primary"} btn-sm" onclick="togglePluginState(${serializeJsArg(plugin.id)}, ${plugin.enabled ? "false" : "true"})">
                ${plugin.enabled ? "Disable" : "Enable"}
              </button>
            </div>
            ${plugin.description ? `<div class="moderation-history-copy">${escapeHtml(plugin.description)}</div>` : ""}
            <div class="detail-list mt-10">
              <div><span>Directory</span><strong>${escapeHtml(plugin.directory)}</strong></div>
              <div><span>Assets</span><strong>${fmtNum(plugin.assetCounts?.styles || 0)} CSS · ${fmtNum(plugin.assetCounts?.scripts || 0)} JS · ${fmtNum(plugin.assetCounts?.assets || 0)} files</strong></div>
              <div><span>Loading Rules</span><strong>Enabled + manifest-declared only</strong></div>
            </div>
          </div>
        `).join("") : renderEmptyState("🧩", "No plugins are installed yet.", "Create plugin folders under /plugins with a plugin.json manifest.")}
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load the plugin manager.", "error");
  }
}

async function togglePluginState(pluginId, enabled) {
  try {
    const data = await API.updatePlugin(pluginId, { enabled });
    if (enabled) {
      await loadEnabledPlugins();
    }
    toast(data.message || "Plugin updated.", "success");
    await showPluginManager();
  } catch (err) {
    toast(err.message || "Could not update that plugin.", "error");
  }
}

async function restoreTrashItem(type, id) {
  try {
    const data = await API.restoreAdminTrash({ type, id });
    toast(data.message || "Item restored.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not restore that item.", "error");
  }
}
