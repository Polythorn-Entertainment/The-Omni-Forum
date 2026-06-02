function splitActionStatements(source) {
  const statements = [];
  let depth = 0;
  let quote = "";
  let current = "";
  for (const char of String(source || "")) {
    if (quote) {
      current += char;
      if (char === quote && !current.endsWith(`\\${quote}`)) quote = "";
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      current += char;
      continue;
    }
    if ("([{".includes(char)) depth += 1;
    if (")]}".includes(char)) depth = Math.max(0, depth - 1);
    if (char === ";" && depth === 0) {
      if (current.trim()) statements.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) statements.push(current.trim());
  return statements;
}

function splitActionArguments(source) {
  const args = [];
  let depth = 0;
  let quote = "";
  let current = "";
  for (const char of String(source || "")) {
    if (quote) {
      current += char;
      if (char === quote && !current.endsWith(`\\${quote}`)) quote = "";
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      current += char;
      continue;
    }
    if ("([{".includes(char)) depth += 1;
    if (")]}".includes(char)) depth = Math.max(0, depth - 1);
    if (char === "," && depth === 0) {
      args.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) args.push(current.trim());
  return args;
}

function parseQuotedActionString(token) {
  const trimmed = String(token || "").trim();
  if (trimmed.length < 2) return trimmed;
  const quote = trimmed[0];
  if ((quote !== "'" && quote !== '"') || trimmed[trimmed.length - 1] !== quote) return trimmed;
  return trimmed
    .slice(1, -1)
    .replaceAll(`\\${quote}`, quote)
    .replaceAll("\\n", "\n")
    .replaceAll("\\t", "\t")
    .replaceAll("\\\\", "\\");
}

function parseActionObject(token, event, node) {
  const body = String(token || "").trim().slice(1, -1);
  const output = {};
  splitActionArguments(body).forEach((part) => {
    const separatorIndex = part.indexOf(":");
    if (separatorIndex < 1) return;
    const key = part.slice(0, separatorIndex).trim().replace(/^['"]|['"]$/g, "");
    output[key] = parseActionArgument(part.slice(separatorIndex + 1), event, node);
  });
  return output;
}

function parseActionArgument(token, event, node) {
  const value = String(token || "").trim();
  if (!value) return "";
  if (value === "event") return event;
  if (value === "this") return node;
  if (value === "this.value") return node?.value ?? "";
  if (value === "true") return true;
  if (value === "false") return false;
  if (value === "null") return null;
  if (value === "undefined") return undefined;
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  if ((value.startsWith("'") && value.endsWith("'")) || (value.startsWith('"') && value.endsWith('"'))) {
    return parseQuotedActionString(value);
  }
  if (value.startsWith("{") && value.endsWith("}")) {
    return parseActionObject(value, event, node);
  }
  return value;
}

function runTrustedInlineAction(source, event, node) {
  let handled = false;
  splitActionStatements(source).forEach((statement) => {
    const match = statement.match(/^([A-Za-z_$][\w$]*)\s*(?:\((.*)\))?$/s);
    if (!match) return;
    const name = match[1];
    const fn = window[name];
    if (typeof fn !== "function") return;
    const args = match[2] ? splitActionArguments(match[2]).map((arg) => parseActionArgument(arg, event, node)) : [];
    handled = true;
    fn(...args);
  });
  return handled;
}

function delegatedInlineAction(event, attributeName) {
  const node = event.target?.closest?.(`[${attributeName}]`);
  if (!node) return;
  const source = node.getAttribute(attributeName) || "";
  const handled = runTrustedInlineAction(source, event, node);
  if (!handled) return;
  if (event.type === "click") {
    const tag = node.tagName;
    if (tag === "BUTTON" || node.getAttribute("href") === "#") {
      event.preventDefault();
    }
    event.stopPropagation();
  }
  if (event.type === "submit") {
    event.preventDefault();
  }
}

document.addEventListener("click", (event) => delegatedInlineAction(event, "onclick"), true);
document.addEventListener("input", (event) => delegatedInlineAction(event, "oninput"), true);
document.addEventListener("change", (event) => delegatedInlineAction(event, "onchange"), true);
document.addEventListener("submit", (event) => delegatedInlineAction(event, "onsubmit"), true);
