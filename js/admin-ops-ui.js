/* Admin operations dashboard, backups, and media cleanup UI */

async function showAdminOpsModal() {
  if (!Auth.isAdmin()) {
    toast("Only admins and the owner can open operations tools.", "error");
    return;
  }
  openModal(`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">Operations</div>
    <div class="muted-copy">Loading health and maintenance tools...</div>
  `, { size: "xl" });
  try {
    const healthData = await API.getAdminHealth();
    const logData = await API.getAdminLogs();
    const trashData = await API.getAdminTrash(40);
    const health = healthData.health || {};
    const storage = health.storage || {};
    const runtime = health.runtime || {};
    const queues = health.queues || {};
    const analytics = health.analytics || {};
    const backups = storage.backups || [];
    const trashItems = trashData.items || [];
    const plugins = health.plugins || [];
    const pluginStatus = health.pluginStatus || {};
    const backupStatus = storage.backupStatus || {};
    const mediaUsage = storage.mediaUsage || {};
    const recovery = health.recovery || {};
    const onboarding = health.onboarding || {};
    const installChecks = health.installChecks || {};
    const logSummary = health.logs || {};
    const latestErrors = logSummary.latestErrors || [];
    const databaseFiles = storage.databaseFiles || Object.entries(storage.databases || {}).map(([name, sizeLabel]) => ({ name, sizeLabel, exists: true }));
    const mediaBuckets = mediaUsage.buckets || [];
    const queueTotal = queues.totalOpen ?? ((queues.reports || 0) + (queues.appeals || 0) + (queues.contactNotices || 0) + (queues.registrations || 0));
    const latestBackup = backupStatus.latest || backups[0] || null;
    const restoreScript = recovery.restoreScript || {};
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Operations</div>
      <div class="ops-hero">
        <div>
          <div class="ops-eyebrow">Production Health</div>
          <div class="ops-hero-title">OmniForum runtime snapshot</div>
          <div class="muted-copy">Database, media, queue, plugin, backup, and recovery readiness checks for the live instance.</div>
        </div>
        ${renderOpsBadge(recovery.status || backupStatus.status, recovery.message || backupStatus.statusLabel || "Health checked")}
      </div>
      <div class="ops-kpi-grid">
        ${renderOpsKpi("Database Size", storage.databaseTotalSize || "0B", `${fmtNum(databaseFiles.length)} files tracked`, storage.databaseMissingCount ? "warning" : "healthy")}
        ${renderOpsKpi("Media Usage", mediaUsage.totalSize || "0B", `${fmtNum(mediaUsage.totalFiles || storage.mediaAssets || 0)} files, ${fmtNum(mediaUsage.orphanedFiles || 0)} orphaned`, mediaUsage.orphanedFiles ? "warning" : "healthy")}
        ${renderOpsKpi("Backup Status", backupStatus.statusLabel || "No status", latestBackup ? `Latest: ${formatDateTime(latestBackup.createdAt)}` : "Create the first archive", backupStatus.status)}
        ${renderOpsKpi("Latest Errors", fmtNum(latestErrors.length || 0), latestErrors.length ? `Last: ${formatDateTime(latestErrors[0].time)}` : "No recent failures", latestErrors.length ? "warning" : "healthy")}
        ${renderOpsKpi("Open Queues", fmtNum(queueTotal), queueTotal ? "Staff attention needed" : "All queues clear", queues.status || (queueTotal ? "attention" : "clear"))}
        ${renderOpsKpi("Plugin Status", `${fmtNum(pluginStatus.enabled || 0)} / ${fmtNum(pluginStatus.total || plugins.length)} enabled`, pluginStatus.invalidCount ? `${fmtNum(pluginStatus.invalidCount)} invalid plugin folders` : "Manifests look good", pluginStatus.status)}
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="createAdminBackup()">Create Backup</button>
        <button class="btn btn-outline" onclick="showInstallWizard()">Setup Wizard</button>
        <button class="btn btn-outline" onclick="showAdminExportTools()">Import / Export</button>
        <button class="btn btn-outline" onclick="showStaffWorkflowTools()">Staff Workflows</button>
        <button class="btn btn-outline" onclick="runMediaCleanup()">Cleanup Orphan Media</button>
        <button class="btn btn-outline" onclick="showSignupControls()">Signup Controls</button>
        <button class="btn btn-outline" onclick="showAuditLog()">Audit Log</button>
        <button class="btn btn-outline" onclick="showPluginManager()">Manage Plugins</button>
      </div>
      <div class="ops-tab-row" role="navigation" aria-label="Operations sections">
        <a href="#ops-launch">Launch</a>
        <a href="#ops-health">Health</a>
        <a href="#ops-data">Data</a>
        <a href="#ops-moderation">Moderation</a>
        <a href="#ops-plugins">Plugins</a>
        <a href="#ops-logs">Logs</a>
      </div>
      <div id="ops-health" class="page-section-title mt-18">Health</div>
      <div class="settings-tool-grid ops-dashboard-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Database Storage</div>
          <div class="settings-tool-copy">Total stored SQLite data across the dedicated data folder.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Total", storage.databaseTotalSize || "0B"],
              ["Files", fmtNum(databaseFiles.length)],
              ["Missing", fmtNum(storage.databaseMissingCount || 0)],
            ])}
          </div>
          <div class="ops-mini-list">
            ${databaseFiles.map((item) => `
              <div>
                <span>${escapeHtml(item.name)}</span>
                <strong>${escapeHtml(item.exists === false ? "Missing" : item.sizeLabel || "0B")}</strong>
              </div>
            `).join("")}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Media Usage</div>
          <div class="settings-tool-copy">Upload footprint by bucket, including cleanup candidates.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Total Size", mediaUsage.totalSize || "0B"],
              ["Files", fmtNum(mediaUsage.totalFiles || 0)],
              ["Orphaned", `${fmtNum(mediaUsage.orphanedFiles || 0)} (${mediaUsage.orphanedSize || "0B"})`],
              ["Per-user Quota", `${storage.mediaQuotaBytesLabel || "0B"} / ${fmtNum(storage.mediaQuotaFiles || 0)} files`],
            ])}
          </div>
          <div class="ops-mini-list">
            ${mediaBuckets.map((bucket) => `
              <div>
                <span>${escapeHtml(bucket.label || bucket.bucket)}</span>
                <strong>${fmtNum(bucket.files || 0)} files / ${escapeHtml(bucket.sizeLabel || "0B")}</strong>
              </div>
            `).join("") || '<div><span>No media files</span><strong>0B</strong></div>'}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Backup Status</div>
          <div class="settings-tool-copy">${escapeHtml(backupStatus.check?.message || backupStatus.statusLabel || "Backup status unavailable.")}</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Archives", fmtNum(backupStatus.count || storage.backupCount || 0)],
              ["Total Size", backupStatus.totalSize || storage.backupTotalSize || "0B"],
              ["Latest", latestBackup ? formatDateTime(latestBackup.createdAt) : "Not created"],
              ["Latest Age", backupStatus.latestAgeLabel || "N/A"],
              ["Rotation", `${fmtNum(backupStatus.rotationLimit || 0)} kept`],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Recovery Readiness</div>
          <div class="settings-tool-copy">${escapeHtml(recovery.message || "Recovery readiness has not been checked yet.")}</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Backup Check", recovery.latestBackupCheck?.status ? `${recovery.latestBackupCheck.status} at ${formatDateTime(recovery.latestBackupCheck.checkedAt)}` : "Not checked"],
              ["Restore Script", restoreScript.exists ? (restoreScript.executable ? "Ready" : "Not executable") : "Missing"],
              ["Last Backup", recovery.lastBackupCreated?.time ? formatDateTime(recovery.lastBackupCreated.time) : "No backup log"],
              ["Last Restore Guide", recovery.lastRestoreGuideCheck?.time ? formatDateTime(recovery.lastRestoreGuideCheck.time) : "Not opened"],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Queue Counts</div>
          <div class="settings-tool-copy">Open staff work that may need triage.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Reports", fmtNum(queues.reports || 0)],
              ["Appeals", fmtNum(queues.appeals || 0)],
              ["Contact", fmtNum(queues.contactNotices || 0)],
              ["Registrations", fmtNum(queues.registrations || 0)],
              ["Total Open", fmtNum(queueTotal)],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Plugin Status</div>
          <div class="settings-tool-copy">Safe-loading summary for installed plugin manifests.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Installed", fmtNum(pluginStatus.total || plugins.length)],
              ["Enabled", fmtNum(pluginStatus.enabled || 0)],
              ["Disabled", fmtNum(pluginStatus.disabled || 0)],
              ["With Assets", fmtNum(pluginStatus.withClientAssets || 0)],
              ["Invalid Folders", fmtNum(pluginStatus.invalidCount || 0)],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Runtime</div>
          <div class="settings-tool-copy">Server configuration values visible to admins.</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Started", formatDateTime(health.startedAt)],
              ["Uptime", `${fmtNum(health.uptimeSeconds || 0)}s`],
              ["Public URL", runtime.publicUrl || "Not set"],
              ["Request Limit", runtime.maxRequestSize || String(runtime.maxRequestBytes || 0)],
              ["Secure Cookies", runtime.secureCookies ? "Enabled" : "Disabled"],
              ["Discord Webhook", runtime.discordWebhookConfigured ? "Connected" : "Not configured"],
              ["Email Auth", runtime.emailAuth?.enabled ? (runtime.emailAuth?.configured ? "Enabled" : "Enabled, SMTP missing") : "Disabled"],
              ["Signup Mode", runtime.registration?.mode || "Open"],
              ["Media Processing", runtime.mediaProcessing?.enabled ? "Pillow enabled" : "Not installed"],
              ["Media Scanner", runtime.mediaScanning?.configured ? "Configured" : (runtime.mediaScanning?.required ? "Required but missing" : "Optional")],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Latest Errors</div>
          <div class="settings-tool-copy">Recent failed requests or runtime warnings from the server log.</div>
          <div class="ops-log-list">
            ${renderOpsLogEntries(latestErrors)}
          </div>
        </div>
      </div>
      <div id="ops-launch" class="page-section-title mt-18">Launch Readiness</div>
      <div class="settings-tool-grid ops-dashboard-grid">
        ${renderOpsChecklist("Admin Onboarding Checklist", "First-run setup items for site structure, policies, registration, themes, and backups.", onboarding)}
        ${renderOpsChecklist("Production Install Checker", "Hosting readiness checks for Docker, proxy files, upload folders, cookies, backup tooling, and media processing.", installChecks)}
      </div>
      <div id="ops-data" class="page-section-title mt-18">Data & Recovery</div>
      <div class="muted-copy mb-12">Soft-deleted threads and replies can be restored here. Restore a thread before restoring any reply inside it.</div>
      <div class="moderation-history-list">
        ${trashItems.length ? trashItems.map((item) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(item.title || (item.type === "thread" ? "Deleted thread" : "Deleted reply"))}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(item.type)}</span>
                  <span>${escapeHtml(formatDateTime(item.deletedAt))}</span>
                  ${item.section?.name ? `<span>${escapeHtml(item.section.name)}</span>` : ""}
                  ${item.threadTitle ? `<span>${escapeHtml(item.threadTitle)}</span>` : ""}
                </div>
              </div>
              <button class="btn btn-outline btn-sm" onclick="restoreTrashItem(${serializeJsArg(item.type)}, ${JSON.stringify(item.id)})">Restore</button>
            </div>
            ${item.preview ? `<div class="moderation-history-copy">${escapeHtml(item.preview)}</div>` : ""}
            <div class="tiny-copy">Deleted by ${escapeHtml(item.deletedBy?.username || "Unknown")} · ${escapeHtml(item.deleteReason || "No reason noted.")}</div>
          </div>
        `).join("") : renderEmptyState("🧺", "Trash is empty right now.")}
      </div>
      <div class="page-section-title mt-18">Backup Archives</div>
      <div class="moderation-history-list">
        ${backups.length ? backups.map((item) => `
          <div class="moderation-history-card">
            <div class="moderation-history-head">
              <div>
                <div class="moderation-history-title">${escapeHtml(item.filename)}</div>
                <div class="moderation-history-meta">
                  <span>${escapeHtml(item.sizeLabel || "—")}</span>
                  <span>${escapeHtml(formatDateTime(item.createdAt))}</span>
                </div>
              </div>
              <div class="stack-actions">
                <button class="btn btn-ghost btn-sm" onclick="showBackupGuide(${serializeJsArg(item.filename)})">Restore Guide</button>
                <a class="btn btn-outline btn-sm" href="${escapeHtml(item.downloadUrl)}" target="_blank" rel="noreferrer">Download</a>
              </div>
            </div>
          </div>
        `).join("") : '<div class="centered-message settings-empty-block">No backups created yet.</div>'}
      </div>
      <div id="ops-plugins" class="page-section-title mt-18">Forum Analytics</div>
      <div class="settings-tool-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">7-Day Activity</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Signups", fmtNum((analytics.registrations7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Active Users", fmtNum((analytics.activeUsers7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Threads", fmtNum((analytics.threads7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Posts", fmtNum((analytics.posts7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
              ["Searches", fmtNum((analytics.searches7d || []).reduce((sum, item) => sum + Number(item.count || 0), 0))],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Search Terms (30d)</div>
          <div class="detail-list">
            ${(analytics.topSearchTerms30d || []).length ? (analytics.topSearchTerms30d || []).map((item) => `<div><span>${escapeHtml(item.query)}</span><strong>${fmtNum(item.count)} searches</strong></div>`).join("") : "<div><span>No searches logged</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Storage Footprint</div>
          <div class="detail-list">
            ${renderOpsDetailRows([
              ["Databases", analytics.storageFootprint?.databases || storage.databaseTotalSize || "0B"],
              ["Media", analytics.storageFootprint?.media || mediaUsage.totalSize || "0B"],
              ["Backups", backupStatus.totalSize || storage.backupTotalSize || "0B"],
            ])}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Popular Tags</div>
          <div class="detail-list">
            ${(analytics.topTags || []).length ? (analytics.topTags || []).slice(0, 8).map((item) => `<div><span>#${escapeHtml(item.tag)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No tag data</span><strong>—</strong></div>"}
          </div>
        </div>
      </div>
      <div id="ops-moderation" class="page-section-title mt-18">Moderation Audit</div>
      <div class="settings-tool-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Active Restrictions</div>
          <div class="detail-list">
            <div><span>Banned</span><strong>${fmtNum(analytics.activeRestrictions?.banned || 0)}</strong></div>
            <div><span>Timed Out</span><strong>${fmtNum(analytics.activeRestrictions?.timedOut || 0)}</strong></div>
            <div><span>Muted</span><strong>${fmtNum(analytics.activeRestrictions?.muted || 0)}</strong></div>
            <div><span>Shadow Muted</span><strong>${fmtNum(analytics.activeRestrictions?.shadowMuted || 0)}</strong></div>
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Moderators (30d)</div>
          <div class="detail-list">
            ${(analytics.topModerators30d || []).length ? (analytics.topModerators30d || []).map((item) => `<div><span>${escapeHtml(item.username)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No staff actions</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Open Report Priorities</div>
          <div class="detail-list">
            ${(analytics.openReportPriorities || []).length ? (analytics.openReportPriorities || []).map((item) => `<div><span>${escapeHtml(item.priority)}</span><strong>${fmtNum(item.count)}</strong></div>`).join("") : "<div><span>No open reports</span><strong>0</strong></div>"}
          </div>
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Top Sections</div>
          <div class="detail-list">
            ${(analytics.topSections || []).length ? (analytics.topSections || []).slice(0, 5).map((item) => `<div><span>${escapeHtml(item.name)}</span><strong>${fmtNum(item.posts || 0)} posts</strong></div>`).join("") : "<div><span>No section data</span><strong>—</strong></div>"}
          </div>
        </div>
      </div>
      <div id="ops-logs" class="page-section-title mt-18">Recent Logs</div>
      <pre class="forum-code-block admin-log-block"><code>${escapeHtml((logData.logs || []).join("\n") || "No logs yet.")}</code></pre>
    `, { size: "xl" });
  } catch (err) {
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Operations</div>
      ${modalError(err.message || "Could not load operations tools.")}
    `, { size: "lg" });
  }
}

async function createAdminBackup() {
  try {
    const data = await API.createBackup();
    if (data.downloadUrl) {
      window.open(data.downloadUrl, "_blank", "noopener");
    }
    toast(data.message || "Backup created.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not create a backup.", "error");
  }
}

async function showBackupGuide(filename) {
  try {
    const data = await API.getBackupGuide(filename);
    const guide = data.guide || {};
    const contents = guide.contents || {};
    const restore = guide.restore || {};
    openModal(`
      <button class="modal-close" onclick="closeModal()">✕</button>
      <div class="modal-title">Restore Guide</div>
      <div class="muted-copy">Use this checklist before restoring ${escapeHtml(guide.filename || filename)} over live data.</div>
      <div class="detail-list mt-16">
        <div><span>Archive</span><strong>${escapeHtml(guide.filename || filename)}</strong></div>
        <div><span>Size</span><strong>${escapeHtml(guide.sizeLabel || "—")}</strong></div>
        <div><span>Created</span><strong>${escapeHtml(formatDateTime(guide.createdAt))}</strong></div>
        <div><span>Databases</span><strong>${fmtNum(contents.databaseCount || 0)}</strong></div>
        <div><span>Uploads</span><strong>${fmtNum(contents.mediaCount || 0)}</strong></div>
      </div>
      ${contents.missingDatabases?.length ? `<div class="form-error visible mt-14">Missing DB files: ${escapeHtml(contents.missingDatabases.join(", "))}</div>` : ""}
      <div class="page-section-title mt-18">Checklist</div>
      <div class="detail-list">
        ${(restore.checks || []).map((item) => `<div><span>Check</span><strong>${escapeHtml(item)}</strong></div>`).join("")}
      </div>
      <div class="page-section-title mt-18">Steps</div>
      <div class="stack-list">
        ${(restore.steps || []).map((item, index) => `<div class="settings-empty-block"><strong>${index + 1}.</strong> ${escapeHtml(item)}</div>`).join("")}
      </div>
      <div class="page-section-title mt-18">Restore Command</div>
      <pre class="forum-code-block admin-log-block"><code>${escapeHtml(restore.command || "No command available.")}</code></pre>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="copyTextValue(${serializeJsArg(restore.command || "")}, 'Restore command')">Copy Command</button>
        ${guide.downloadUrl ? `<a class="btn btn-primary" href="${escapeHtml(guide.downloadUrl)}" target="_blank" rel="noreferrer">Download Archive</a>` : ""}
      </div>
    `, { size: "lg" });
  } catch (err) {
    toast(err.message || "Could not load that restore guide.", "error");
  }
}

async function runMediaCleanup() {
  try {
    const data = await API.cleanupMedia();
    toast(data.message || "Media cleanup complete.", "success");
    await showAdminOpsModal();
  } catch (err) {
    toast(err.message || "Could not clean up media.", "error");
  }
}
