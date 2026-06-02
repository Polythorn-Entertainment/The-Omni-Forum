async function api(path, body) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? {"Content-Type": "application/json"} : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function byId(id) {
  return document.getElementById(id);
}

function formPayload() {
  return {
    publicUrl: byId("publicUrl").value,
    port: byId("port").value,
    secureCookies: byId("secureCookies").checked,
    emailAuthEnabled: byId("emailAuthEnabled").checked,
    emailFrom: byId("emailFrom").value,
    smtpHost: byId("smtpHost").value,
    deployHost: byId("deployHost").value,
    deployUser: byId("deployUser").value,
    deployPath: byId("deployPath").value,
    deployService: byId("deployService").value,
    deployPublicUrl: byId("deployPublicUrl").value,
    healthcheckUrl: byId("healthcheckUrl").value,
    healthcheckWebhookUrl: byId("healthcheckWebhookUrl").value,
    offsiteTarget: byId("offsiteTarget").value,
    backupPasswordFile: byId("backupPasswordFile").value,
    url: byId("url").value,
    confirm: byId("scrubConfirm").value,
  };
}

function setOutput(text) {
  byId("output").textContent = text || "";
}

async function refreshStatus() {
  const data = await api("/api/status");
  const runtime = data.runtimePrivateFiles.length
    ? `<span class="pill warn">runtime files: ${data.runtimePrivateFiles.length}</span>`
    : `<span class="pill ok">runtime clean</span>`;
  byId("status").innerHTML = [
    runtime,
    `<span class="pill ${data.envFiles.runtime ? "warn" : "ok"}">.env ${data.envFiles.runtime ? "present" : "absent"}</span>`,
    `<span class="pill ${data.dockerAvailable ? "ok" : "warn"}">docker ${data.dockerAvailable ? "available" : "not detected"}</span>`,
    `<span class="pill ok">package ${data.latestPackage || "not built yet"}</span>`,
  ].join("");
}

async function writeEnv(kind) {
  setOutput(`Writing ${kind} env...`);
  const data = await api("/api/write-env", {kind, payload: formPayload()});
  setOutput(data.message + "\n" + data.path);
  refreshStatus();
}

async function runAction(action) {
  setOutput(`Running ${action}...`);
  try {
    const data = await api("/api/run", {action, payload: formPayload()});
    setOutput(`${data.ok ? "OK" : "FAILED"} ${data.command || action}\n\n${data.output || ""}`);
  } catch (error) {
    setOutput(`FAILED ${action}\n\n${error.message}`);
  }
  refreshStatus();
}

async function showDeployCommand() {
  const data = await api("/api/status");
  setOutput(data.deployCommand);
}

document.addEventListener("click", (event) => {
  const writeButton = event.target.closest("[data-write-env]");
  if (writeButton) {
    writeEnv(writeButton.dataset.writeEnv);
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (actionButton) {
    runAction(actionButton.dataset.action);
  }
});

byId("showDeployCommand").addEventListener("click", showDeployCommand);
refreshStatus();
