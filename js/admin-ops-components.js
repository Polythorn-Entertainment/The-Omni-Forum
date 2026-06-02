/* Admin operations dashboard, audit log, backups, and media cleanup UI */

function opsStatusTone(status) {
  const value = String(status || "").toLowerCase();
  if (["healthy", "ok", "clear", "ready", "enabled", "success"].includes(value)) return "good";
  if (["error", "critical", "failed", "missing"].includes(value)) return "bad";
  if (["attention", "warning", "warn", "stale"].includes(value)) return "warn";
  return "neutral";
}

function renderOpsBadge(status, label) {
  return `<span class="ops-status-badge ${opsStatusTone(status)}">${escapeHtml(label || status || "Unknown")}</span>`;
}

function renderOpsKpi(label, value, hint = "", status = "neutral") {
  return `
    <div class="ops-kpi-card ${opsStatusTone(status)}">
      <div class="ops-kpi-label">${escapeHtml(label)}</div>
      <div class="ops-kpi-value">${escapeHtml(value)}</div>
      ${hint ? `<div class="ops-kpi-hint">${escapeHtml(hint)}</div>` : ""}
    </div>
  `;
}

function renderOpsDetailRows(rows = []) {
  return rows
    .filter((row) => row && row.length >= 2)
    .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderOpsLogEntries(entries = []) {
  if (!entries.length) {
    return '<div class="settings-empty-block">No recent errors or failed requests in the runtime log.</div>';
  }
  return entries.map((entry) => `
    <div class="ops-log-entry">
      <div class="ops-log-meta">
        ${entry.status ? `<span>HTTP ${escapeHtml(String(entry.status))}</span>` : "<span>Runtime</span>"}
        <span>${escapeHtml(formatDateTime(entry.time))}</span>
      </div>
      <code>${escapeHtml(entry.line || "")}</code>
    </div>
  `).join("");
}

function renderOpsChecklist(title, summary, checklist = {}) {
  const items = checklist.items || [];
  return `
    <div class="settings-tool-card ops-check-card">
      <div class="settings-tool-title">${escapeHtml(title)}</div>
      <div class="settings-tool-copy">${escapeHtml(summary)}</div>
      <div class="ops-check-progress">
        ${renderOpsBadge(checklist.status || "attention", `${fmtNum(checklist.complete ?? checklist.passing ?? 0)} / ${fmtNum(checklist.total || items.length)} ready`)}
      </div>
      <div class="ops-check-list">
        ${items.map((item) => `
          <div class="ops-check-item ${item.ok ? "ok" : "attention"}">
            <span>${item.ok ? "✓" : "!"}</span>
            <div>
              <strong>${escapeHtml(item.label)}</strong>
              <small>${escapeHtml(item.detail || "")}</small>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function formatAuditLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
