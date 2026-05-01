const DB = {
  roles: {
    owner: { label: "Owner", icon: "👑", level: 5, color: "#ff6b6b", cssClass: "owner" },
    admin: { label: "Admin", icon: "⚡", level: 4, color: "#ff9f9f", cssClass: "admin" },
    mod: { label: "Mod", icon: "🛡️", level: 3, color: "#00d4ff", cssClass: "mod" },
    veteran: { label: "Veteran", icon: "⭐", level: 2, color: "#b39ddb", cssClass: "veteran" },
    member: { label: "Member", icon: "💎", level: 1, color: "#6b7a94", cssClass: "member" },
    new: { label: "New", icon: "🌱", level: 0, color: "#06d6a0", cssClass: "new" },
  },

  setRoles(roles) {
    if (roles && typeof roles === "object") {
      this.roles = roles;
    }
  },

  getRoleLevel(role) {
    return this.roles[role]?.level ?? 0;
  },

  getXPForNextLevel(xp) {
    const thresholds = [
      { label: "New", min: 0, next: 100 },
      { label: "Member", min: 100, next: 600 },
      { label: "Veteran", min: 600, next: 2000 },
      { label: "Established", min: 2000, next: 5000 },
      { label: "Elite", min: 5000, next: Infinity },
    ];

    for (let index = 0; index < thresholds.length; index += 1) {
      const current = thresholds[index];
      if (xp < current.next) {
        return {
          current: xp - current.min,
          needed: Number.isFinite(current.next) ? current.next - current.min : 1,
          label: current.label,
          nextLabel: thresholds[index + 1]?.label || "Elite",
        };
      }
    }

    return { current: 1, needed: 1, label: "Elite", nextLabel: "Elite" };
  },
};

const SITE_THEME_STORAGE_KEY = "omniforum:site-theme";
const SITE_THEMES = {
  midnight: {
    label: "Midnight Signal",
    description: "The default OmniForum look with deep graphite panels and neon blue accents.",
    preview: ["#131920", "#00d4ff", "#7b5ea7", "#ffd166"],
    vars: {
      "--bg": "#080b10",
      "--bg2": "#0d1117",
      "--bg3": "#131920",
      "--bg4": "#1a2230",
      "--border": "rgba(255,255,255,0.07)",
      "--border-hover": "rgba(255,255,255,0.15)",
      "--text": "#e8edf5",
      "--text-muted": "#6b7a94",
      "--text-dim": "#3d4f68",
      "--accent": "#00d4ff",
      "--accent2": "#7b5ea7",
      "--accent3": "#ff6b6b",
      "--accent4": "#ffd166",
      "--accent5": "#06d6a0",
      "--glow": "rgba(0,212,255,0.15)",
    },
  },
  ember: {
    label: "Ember Relay",
    description: "Warm copper and magenta tones over a charcoal-red base.",
    preview: ["#241618", "#ff815d", "#ff4f9a", "#ffb347"],
    vars: {
      "--bg": "#120b0b",
      "--bg2": "#1a1112",
      "--bg3": "#241618",
      "--bg4": "#322022",
      "--border": "rgba(255,177,153,0.08)",
      "--border-hover": "rgba(255,177,153,0.18)",
      "--text": "#f6ede7",
      "--text-muted": "#a6867c",
      "--text-dim": "#6c514b",
      "--accent": "#ff815d",
      "--accent2": "#ff4f9a",
      "--accent3": "#ff6b6b",
      "--accent4": "#ffb347",
      "--accent5": "#6be3c1",
      "--glow": "rgba(255,129,93,0.18)",
    },
  },
  verdant: {
    label: "Verdant Wire",
    description: "A cool forest palette with bright mint and botanical greens.",
    preview: ["#132019", "#4de0a8", "#12b886", "#c3f73a"],
    vars: {
      "--bg": "#08100d",
      "--bg2": "#0d1713",
      "--bg3": "#132019",
      "--bg4": "#1b2d24",
      "--border": "rgba(120,214,171,0.08)",
      "--border-hover": "rgba(120,214,171,0.18)",
      "--text": "#e6f5ee",
      "--text-muted": "#76a391",
      "--text-dim": "#456558",
      "--accent": "#4de0a8",
      "--accent2": "#12b886",
      "--accent3": "#f28f3b",
      "--accent4": "#c3f73a",
      "--accent5": "#7dffb3",
      "--glow": "rgba(77,224,168,0.18)",
    },
  },
  sunset: {
    label: "Sunset Circuit",
    description: "Soft violet panels with apricot, gold, and pink highlights.",
    preview: ["#211827", "#ff9f6e", "#c084fc", "#ffd166"],
    vars: {
      "--bg": "#100b12",
      "--bg2": "#18111b",
      "--bg3": "#211827",
      "--bg4": "#2d2136",
      "--border": "rgba(255,201,142,0.08)",
      "--border-hover": "rgba(255,201,142,0.18)",
      "--text": "#f5eef8",
      "--text-muted": "#9d8aa9",
      "--text-dim": "#61506c",
      "--accent": "#ff9f6e",
      "--accent2": "#c084fc",
      "--accent3": "#ff6b9a",
      "--accent4": "#ffd166",
      "--accent5": "#7ee7c1",
      "--glow": "rgba(255,159,110,0.18)",
    },
  },
  arctic: {
    label: "Arctic Glass",
    description: "An icy blue scheme with crisp panels and bright glassy highlights.",
    preview: ["#13202c", "#6dd3ff", "#8ab4ff", "#9fe870"],
    vars: {
      "--bg": "#081018",
      "--bg2": "#0d1621",
      "--bg3": "#13202c",
      "--bg4": "#1c2d3d",
      "--border": "rgba(160,218,255,0.10)",
      "--border-hover": "rgba(160,218,255,0.22)",
      "--text": "#edf6ff",
      "--text-muted": "#7f98b3",
      "--text-dim": "#556a82",
      "--accent": "#6dd3ff",
      "--accent2": "#8ab4ff",
      "--accent3": "#ff7a90",
      "--accent4": "#9fe870",
      "--accent5": "#7cf0d0",
      "--glow": "rgba(109,211,255,0.20)",
    },
  },
  aurora: {
    label: "Aurora Bloom",
    description: "Northern-light greens and violets sweeping across deep twilight panels.",
    preview: ["#161b2f", "#70f0c2", "#9b8cff", "#d7ff70"],
    vars: {
      "--bg": "#080b14",
      "--bg2": "#0f1420",
      "--bg3": "#161b2f",
      "--bg4": "#202844",
      "--border": "rgba(132,214,214,0.09)",
      "--border-hover": "rgba(132,214,214,0.22)",
      "--text": "#eef4ff",
      "--text-muted": "#8392ba",
      "--text-dim": "#566483",
      "--accent": "#70f0c2",
      "--accent2": "#9b8cff",
      "--accent3": "#ff7da6",
      "--accent4": "#d7ff70",
      "--accent5": "#7ee7ff",
      "--glow": "rgba(112,240,194,0.18)",
    },
  },
  cobaltforge: {
    label: "Cobalt Forge",
    description: "Forged navy panels lit by cobalt signals, amber rails, and molten coral sparks.",
    preview: ["#132033", "#5b8cff", "#f4b860", "#ff7a7a"],
    vars: {
      "--bg": "#08111c",
      "--bg2": "#0d1726",
      "--bg3": "#132033",
      "--bg4": "#1c2d47",
      "--border": "rgba(120,160,255,0.10)",
      "--border-hover": "rgba(120,160,255,0.24)",
      "--text": "#eef3ff",
      "--text-muted": "#7f93b8",
      "--text-dim": "#536682",
      "--accent": "#5b8cff",
      "--accent2": "#f4b860",
      "--accent3": "#ff7a7a",
      "--accent4": "#8dd35f",
      "--accent5": "#7ee7ff",
      "--glow": "rgba(91,140,255,0.20)",
    },
  },
  matchawire: {
    label: "Matcha Wire",
    description: "Dark olive panels with citrus greens, soft gold, and warm orange highlights.",
    preview: ["#1b2416", "#b9e769", "#7ac74f", "#f4d35e"],
    vars: {
      "--bg": "#0b1008",
      "--bg2": "#131a10",
      "--bg3": "#1b2416",
      "--bg4": "#26331f",
      "--border": "rgba(198,214,132,0.09)",
      "--border-hover": "rgba(198,214,132,0.20)",
      "--text": "#f2f7e8",
      "--text-muted": "#98a17b",
      "--text-dim": "#667050",
      "--accent": "#b9e769",
      "--accent2": "#7ac74f",
      "--accent3": "#ff8f66",
      "--accent4": "#f4d35e",
      "--accent5": "#b8f2e6",
      "--glow": "rgba(185,231,105,0.18)",
    },
  },
  ultraviolet: {
    label: "Ultraviolet Drift",
    description: "Saturated indigo panels with electric cyan, magenta bloom, and gold signal peaks.",
    preview: ["#19122b", "#b888ff", "#6fe7ff", "#ffe066"],
    vars: {
      "--bg": "#090714",
      "--bg2": "#110d1e",
      "--bg3": "#19122b",
      "--bg4": "#241b3e",
      "--border": "rgba(180,136,255,0.09)",
      "--border-hover": "rgba(180,136,255,0.22)",
      "--text": "#f1ecff",
      "--text-muted": "#978cb8",
      "--text-dim": "#63587f",
      "--accent": "#b888ff",
      "--accent2": "#6fe7ff",
      "--accent3": "#ff6fae",
      "--accent4": "#ffe066",
      "--accent5": "#8dffda",
      "--glow": "rgba(184,136,255,0.18)",
    },
  },
  rosewater: {
    label: "Rosewater Pulse",
    description: "Soft rose panels with cherry highlights and warm gold signal lights.",
    preview: ["#24151d", "#ff7da6", "#ffb3c6", "#ffd166"],
    vars: {
      "--bg": "#10080d",
      "--bg2": "#181019",
      "--bg3": "#24151d",
      "--bg4": "#32202a",
      "--border": "rgba(255,182,197,0.08)",
      "--border-hover": "rgba(255,182,197,0.18)",
      "--text": "#f9eef2",
      "--text-muted": "#ac8996",
      "--text-dim": "#6d5160",
      "--accent": "#ff7da6",
      "--accent2": "#ffb3c6",
      "--accent3": "#ff5c7c",
      "--accent4": "#ffd166",
      "--accent5": "#87f5c8",
      "--glow": "rgba(255,125,166,0.18)",
    },
  },
  deepsea: {
    label: "Deepsea Current",
    description: "Ocean-floor blues with aqua signals and teal-glass surfaces.",
    preview: ["#10212b", "#38d9a9", "#3bc9db", "#74c0fc"],
    vars: {
      "--bg": "#061018",
      "--bg2": "#0c1821",
      "--bg3": "#10212b",
      "--bg4": "#193341",
      "--border": "rgba(96,197,214,0.10)",
      "--border-hover": "rgba(96,197,214,0.22)",
      "--text": "#e9f7fb",
      "--text-muted": "#7fa0ad",
      "--text-dim": "#526c78",
      "--accent": "#38d9a9",
      "--accent2": "#3bc9db",
      "--accent3": "#ff8c69",
      "--accent4": "#74c0fc",
      "--accent5": "#9cffd0",
      "--glow": "rgba(59,201,219,0.20)",
    },
  },
  dune: {
    label: "Dune Static",
    description: "Desert sand tones over smoked bronze panels with sunlit accents.",
    preview: ["#221a12", "#f4a261", "#e9c46a", "#84cc16"],
    vars: {
      "--bg": "#110c08",
      "--bg2": "#18120d",
      "--bg3": "#221a12",
      "--bg4": "#302418",
      "--border": "rgba(240,198,140,0.08)",
      "--border-hover": "rgba(240,198,140,0.18)",
      "--text": "#f7efe4",
      "--text-muted": "#a18d74",
      "--text-dim": "#6e5b46",
      "--accent": "#f4a261",
      "--accent2": "#e9c46a",
      "--accent3": "#e76f51",
      "--accent4": "#84cc16",
      "--accent5": "#f6d365",
      "--glow": "rgba(244,162,97,0.18)",
    },
  },
  reactor: {
    label: "Reactor Core",
    description: "Industrial dark steel with toxic lime, cyan, and warning amber.",
    preview: ["#181b1f", "#a3e635", "#22d3ee", "#f59e0b"],
    vars: {
      "--bg": "#090b0d",
      "--bg2": "#111418",
      "--bg3": "#181b1f",
      "--bg4": "#242930",
      "--border": "rgba(200,214,90,0.08)",
      "--border-hover": "rgba(200,214,90,0.18)",
      "--text": "#f1f5f9",
      "--text-muted": "#8a97a5",
      "--text-dim": "#5e6873",
      "--accent": "#a3e635",
      "--accent2": "#22d3ee",
      "--accent3": "#f97316",
      "--accent4": "#f59e0b",
      "--accent5": "#4ade80",
      "--glow": "rgba(163,230,53,0.18)",
    },
  },
  lilacstorm: {
    label: "Lilac Storm",
    description: "Stormy violet panels charged with electric lavender and coral.",
    preview: ["#1d1827", "#a78bfa", "#f472b6", "#facc15"],
    vars: {
      "--bg": "#0e0a13",
      "--bg2": "#15101c",
      "--bg3": "#1d1827",
      "--bg4": "#2a2136",
      "--border": "rgba(184,167,255,0.08)",
      "--border-hover": "rgba(184,167,255,0.18)",
      "--text": "#f4efff",
      "--text-muted": "#9a8bb1",
      "--text-dim": "#655977",
      "--accent": "#a78bfa",
      "--accent2": "#f472b6",
      "--accent3": "#fb7185",
      "--accent4": "#facc15",
      "--accent5": "#67e8f9",
      "--glow": "rgba(167,139,250,0.18)",
    },
  },
  monolith: {
    label: "Monolith Mono",
    description: "A stripped-back graphite scheme with silver highlights and a single amber spark.",
    preview: ["#161616", "#d4d4d4", "#8b8b8b", "#fbbf24"],
    vars: {
      "--bg": "#070707",
      "--bg2": "#101010",
      "--bg3": "#161616",
      "--bg4": "#232323",
      "--border": "rgba(255,255,255,0.06)",
      "--border-hover": "rgba(255,255,255,0.16)",
      "--text": "#f3f4f6",
      "--text-muted": "#8b8b8b",
      "--text-dim": "#5c5c5c",
      "--accent": "#d4d4d4",
      "--accent2": "#9ca3af",
      "--accent3": "#f87171",
      "--accent4": "#fbbf24",
      "--accent5": "#86efac",
      "--glow": "rgba(212,212,212,0.12)",
    },
  },
  ivorysignal: {
    label: "Ivory Signal",
    description: "A bright porcelain light theme with crisp navy type and luminous cyan signal lines.",
    preview: ["#f7f4ec", "#0f2741", "#00a8cc", "#f4b942"],
    vars: {
      "--bg": "#f6f2ea",
      "--bg2": "#fbf8f2",
      "--bg3": "#ffffff",
      "--bg4": "#e8dfd1",
      "--border": "rgba(15,39,65,0.10)",
      "--border-hover": "rgba(15,39,65,0.22)",
      "--text": "#162334",
      "--text-muted": "#617186",
      "--text-dim": "#94a0af",
      "--accent": "#00a8cc",
      "--accent2": "#265d8d",
      "--accent3": "#e86a5b",
      "--accent4": "#f4b942",
      "--accent5": "#37b48f",
      "--glow": "rgba(0,168,204,0.14)",
    },
  },
  seaglass: {
    label: "Seaglass Day",
    description: "A soft aqua light mode with frosted surfaces, cool ink, and coastal teal accents.",
    preview: ["#eef8f7", "#1c4958", "#27b1b8", "#8bcf7b"],
    vars: {
      "--bg": "#eaf6f4",
      "--bg2": "#f4fbfa",
      "--bg3": "#ffffff",
      "--bg4": "#d6ebe7",
      "--border": "rgba(28,73,88,0.10)",
      "--border-hover": "rgba(28,73,88,0.20)",
      "--text": "#17323c",
      "--text-muted": "#5d7a82",
      "--text-dim": "#8aa1a6",
      "--accent": "#27b1b8",
      "--accent2": "#1c7c8d",
      "--accent3": "#f28f6b",
      "--accent4": "#8bcf7b",
      "--accent5": "#5f6df5",
      "--glow": "rgba(39,177,184,0.14)",
    },
  },
  petalpaper: {
    label: "Petal Paper",
    description: "A warm editorial light theme with blush paper panels and plum, coral, and gold highlights.",
    preview: ["#f9f1ef", "#5b3156", "#e7797d", "#f2c14e"],
    vars: {
      "--bg": "#f8efec",
      "--bg2": "#fdf8f6",
      "--bg3": "#fffdfc",
      "--bg4": "#ead9d6",
      "--border": "rgba(91,49,86,0.10)",
      "--border-hover": "rgba(91,49,86,0.22)",
      "--text": "#31203a",
      "--text-muted": "#735e77",
      "--text-dim": "#a897a8",
      "--accent": "#c3558b",
      "--accent2": "#5b3156",
      "--accent3": "#e7797d",
      "--accent4": "#f2c14e",
      "--accent5": "#3ea58a",
      "--glow": "rgba(195,85,139,0.14)",
    },
  },
};

const SUPPORTED_IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const SUPPORTED_IMAGE_NAME = /\.(png|jpe?g|gif|webp)$/i;
const ALLOWED_REACTIONS = ["👍", "❤️", "😂", "🎉", "🔥", "👀"];
const UPLOAD_LIMITS = {
  avatarBytes: 3 * 1024 * 1024,
  postBytes: 8 * 1024 * 1024,
  postCount: 4,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNum(value) {
  const amount = Number(value || 0);
  if (amount >= 1000000) return `${(amount / 1000000).toFixed(1)}m`;
  if (amount >= 1000) return `${(amount / 1000).toFixed(1)}k`;
  return String(amount);
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatRelativeTime(value) {
  if (!value) return "just now";
  const then = new Date(value).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

function initialsForUser(user) {
  const username = typeof user === "string" ? user : user?.username;
  return (username || "NX").slice(0, 2).toUpperCase();
}

function resolveSiteTheme(themeId) {
  return SITE_THEMES[themeId] ? themeId : "midnight";
}

function applySiteTheme(themeId, options = {}) {
  const resolved = resolveSiteTheme(themeId);
  const theme = SITE_THEMES[resolved];
  const root = document.documentElement;
  Object.entries(theme.vars).forEach(([name, value]) => {
    root.style.setProperty(name, value);
  });
  root.dataset.siteTheme = resolved;

  try {
    if (options.storage === "set") {
      window.localStorage.setItem(SITE_THEME_STORAGE_KEY, resolved);
    } else if (options.storage === "clear") {
      window.localStorage.removeItem(SITE_THEME_STORAGE_KEY);
    }
  } catch {
    // Ignore localStorage failures.
  }
  return resolved;
}

function applyInitialSiteTheme() {
  let stored = "midnight";
  try {
    stored = window.localStorage.getItem(SITE_THEME_STORAGE_KEY) || "midnight";
  } catch {
    stored = "midnight";
  }
  applySiteTheme(stored, { storage: "ignore" });
}

function splitLines(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .trim()
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function humanFileSize(bytes) {
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) return `${mb.toFixed(mb >= 10 ? 0 : 1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

function buildAltFromFilename(name) {
  return String(name || "Forum image")
    .replace(/\.[^.]+$/, "")
    .replace(/[-_]+/g, " ")
    .trim()
    .slice(0, 120) || "Forum image";
}

function isSupportedImageFile(file) {
  return SUPPORTED_IMAGE_TYPES.has(file?.type) || SUPPORTED_IMAGE_NAME.test(file?.name || "");
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file?.name || "that file"}.`));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsDataURL(file);
  });
}

async function readImageUploads(files, options = {}) {
  const items = Array.from(files || []).filter(Boolean);
  const maxFiles = options.maxFiles ?? UPLOAD_LIMITS.postCount;
  const maxBytes = options.maxBytes ?? UPLOAD_LIMITS.postBytes;
  const field = options.field || "Images";
  if (!items.length) return [];
  if (items.length > maxFiles) {
    if (maxFiles <= 0) {
      throw new Error(`Remove an existing image before adding more ${field.toLowerCase()}.`);
    }
    throw new Error(`${field} supports up to ${maxFiles} file${maxFiles === 1 ? "" : "s"} at once.`);
  }

  return Promise.all(items.map(async (file) => {
    if (!isSupportedImageFile(file)) {
      throw new Error(`Only PNG, JPG, GIF, and WEBP files are supported for ${field.toLowerCase()}.`);
    }
    if ((file.size || 0) > maxBytes) {
      throw new Error(`${file.name} is too large. Keep each file under ${humanFileSize(maxBytes)}.`);
    }
    return {
      name: file.name,
      alt: buildAltFromFilename(file.name),
      dataUrl: await readFileAsDataUrl(file),
    };
  }));
}

async function readSingleImageUpload(files, options = {}) {
  const uploads = await readImageUploads(files, { ...options, maxFiles: 1 });
  return uploads[0] || null;
}

function renderInlineMedia(media = [], options = {}) {
  const items = Array.isArray(media) ? media.filter((item) => item?.url) : [];
  if (!items.length) return "";
  const sensitive = Boolean(options.sensitive);
  const blurMedia = Boolean(options.blurMedia);
  return `
    <div class="inline-media-grid${items.length === 1 ? " single" : ""}${sensitive ? " sensitive" : ""}${blurMedia ? " sensitive-blur" : ""}">
      ${items.map((item) => `
        <figure class="inline-media-card-wrap${sensitive && blurMedia ? " sensitive-media-card blurred" : ""}">
          <a class="inline-media-card" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">
            <img src="${escapeHtml(item.thumbnailUrl || item.url)}" alt="${escapeHtml(item.alt || "Forum image")}" loading="lazy">
          </a>
          ${sensitive && blurMedia ? '<button class="sensitive-media-toggle" type="button" onclick="toggleSensitiveMedia(event)">Reveal media</button>' : ""}
          ${item.alt ? `<figcaption class="inline-media-caption">${escapeHtml(item.alt)}</figcaption>` : ""}
        </figure>
      `).join("")}
    </div>
  `;
}

function preprocessForumMarkup(text) {
  return String(text || "")
    .replace(/\[quote=([^\]]+)\]([\s\S]*?)\[\/quote\]/gi, (_, author, body) => {
      return `> ${String(author || "").trim()} wrote:\n> ${String(body || "").trim().replace(/\n/g, "\n> ")}`;
    })
    .replace(/\[quote\]([\s\S]*?)\[\/quote\]/gi, (_, body) => `> ${String(body || "").trim().replace(/\n/g, "\n> ")}`)
    .replace(/\[code\]([\s\S]*?)\[\/code\]/gi, (_, body) => `\n\`\`\`\n${String(body || "").trim()}\n\`\`\`\n`)
    .replace(/\[b\]([\s\S]*?)\[\/b\]/gi, "**$1**")
    .replace(/\[i\]([\s\S]*?)\[\/i\]/gi, "*$1*")
    .replace(/\[u\]([\s\S]*?)\[\/u\]/gi, "<u>$1</u>")
    .replace(/\[s\]([\s\S]*?)\[\/s\]/gi, "~~$1~~")
    .replace(/\[spoiler\]([\s\S]*?)\[\/spoiler\]/gi, '<span class="forum-spoiler">$1</span>')
    .replace(/\[url=([^\]]+)\]([\s\S]*?)\[\/url\]/gi, "[$2]($1)");
}

function applyInlineFormatting(raw) {
  let text = escapeHtml(raw || "");
  text = text.replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/gi, '<span class="forum-underline">$1</span>');
  text = text.replace(/&lt;span class=&quot;forum-spoiler&quot;&gt;([\s\S]*?)&lt;\/span&gt;/gi, '<span class="forum-spoiler">$1</span>');
  text = text.replace(/`([^`]+?)`/g, '<code class="inline-code">$1</code>');
  text = text.replace(/\*\*([^*]+?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__([^_]+?)__/g, "<strong>$1</strong>");
  text = text.replace(/(^|[^\*])\*([^*\n]+?)\*(?!\*)/g, "$1<em>$2</em>");
  text = text.replace(/(^|[^_])_([^_\n]+?)_(?!_)/g, "$1<em>$2</em>");
  text = text.replace(/~~([^~]+?)~~/g, "<s>$1</s>");
  text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  text = text.replace(/(^|[\s(])((https?:\/\/|www\.)[^\s<]+)/gi, (_, prefix, match) => {
    const href = match.startsWith("http") ? match : `https://${match}`;
    return `${prefix}<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">${escapeHtml(match)}</a>`;
  });
  text = text.replace(/(^|[^\w-])@([A-Za-z0-9_-]{3,24})/g, '$1<span class="mention-token">@$2</span>');
  return text;
}

function renderMarkupBlocks(text) {
  const normalized = preprocessForumMarkup(text)
    .replace(/\r\n/g, "\n")
    .trim();
  if (!normalized) return "";
  const blocks = normalized.split(/\n{2,}/).filter(Boolean);
  return blocks.map((block) => {
    const lines = block.split("\n");
    if (block.startsWith("```") && block.endsWith("```")) {
      const code = block.replace(/^```/, "").replace(/```$/, "").trim();
      return `<pre class="forum-code-block"><code>${escapeHtml(code)}</code></pre>`;
    }
    if (lines.every((line) => line.trim().startsWith(">"))) {
      const quoteLines = lines.map((line) => line.replace(/^\s*>\s?/, ""));
      return `<blockquote class="forum-quote">${quoteLines.map((line) => applyInlineFormatting(line)).join("<br>")}</blockquote>`;
    }
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return `<ul class="forum-list">${lines.map((line) => `<li>${applyInlineFormatting(line.replace(/^\s*[-*]\s+/, ""))}</li>`).join("")}</ul>`;
    }
    const headingMatch = lines[0].match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = Math.min(3, headingMatch[1].length + 1);
      const remaining = lines.slice(1).join("\n");
      return `
        <div class="forum-heading-block">
          <h${level} class="forum-heading level-${level}">${applyInlineFormatting(headingMatch[2])}</h${level}>
          ${remaining ? `<div class="forum-heading-copy">${applyInlineFormatting(remaining)}</div>` : ""}
        </div>
      `;
    }
    return `<p>${applyInlineFormatting(block).replace(/\n/g, "<br>")}</p>`;
  }).join("");
}

function renderUserContent(text, media = [], options = {}) {
  const copy = renderMarkupBlocks(text);
  const mediaMarkup = renderInlineMedia(media, options);
  if (!copy && !mediaMarkup) {
    return "<p></p>";
  }
  return `${copy}${mediaMarkup}`;
}

function bindDropTarget(dropTarget, fileInput, onFiles) {
  if (!dropTarget || !fileInput) return () => {};
  const prevent = (event) => {
    event.preventDefault();
    event.stopPropagation();
  };
  const onDrop = (event) => {
    prevent(event);
    dropTarget.classList.remove("drag-active");
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) {
      fileInput.files = event.dataTransfer.files;
      if (typeof onFiles === "function") onFiles(files);
    }
  };
  ["dragenter", "dragover"].forEach((name) => dropTarget.addEventListener(name, (event) => {
    prevent(event);
    dropTarget.classList.add("drag-active");
  }));
  ["dragleave", "dragend"].forEach((name) => dropTarget.addEventListener(name, (event) => {
    prevent(event);
    dropTarget.classList.remove("drag-active");
  }));
  dropTarget.addEventListener("drop", onDrop);
  const onKeydown = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    fileInput.click();
  };
  dropTarget.addEventListener("keydown", onKeydown);
  return () => {
    dropTarget.removeEventListener("drop", onDrop);
    dropTarget.removeEventListener("keydown", onKeydown);
  };
}

async function readPastedImageUploads(items, options = {}) {
  const files = Array.from(items || [])
    .map((item) => item?.getAsFile?.())
    .filter((file) => file && isSupportedImageFile(file));
  if (!files.length) return [];
  return readImageUploads(files, options);
}

function bindPasteImageTarget(target, onUploads, options = {}) {
  if (!target || typeof onUploads !== "function") return () => {};
  const handler = async (event) => {
    try {
      const uploads = await readPastedImageUploads(event.clipboardData?.items, options);
      if (!uploads.length) return;
      event.preventDefault();
      await onUploads(uploads, { fromPaste: true });
    } catch (err) {
      if (typeof window.toast === "function") {
        window.toast(err.message || "Could not add the pasted image.", "error");
      }
    }
  };
  target.addEventListener("paste", handler);
  return () => target.removeEventListener("paste", handler);
}

function toggleSensitiveMedia(event) {
  const card = event?.target?.closest(".sensitive-media-card");
  if (!card) return;
  card.classList.toggle("blurred");
  const toggle = card.querySelector(".sensitive-media-toggle");
  if (toggle) {
    toggle.textContent = card.classList.contains("blurred") ? "Reveal media" : "Hide media";
  }
}

function downloadJsonFile(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "omniforum-export.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadTextFile(filename, content, contentType = "text/plain") {
  const blob = new Blob([String(content || "")], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "omniforum-export.txt";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderUploadPreviewList(uploads = [], options = {}) {
  const removeAction = options.removeAction || "";
  const altAction = options.altAction || "";
  if (!uploads.length) {
    return `<div class="upload-preview-empty">Drop images here or use the file picker.</div>`;
  }
  return `
    <div class="upload-preview-grid">
      ${uploads.map((item, index) => `
        <div class="upload-preview-card">
          <div class="upload-preview-image-wrap">
            <img class="upload-preview-image" src="${escapeHtml(item.dataUrl || item.url || "")}" alt="${escapeHtml(item.alt || "Upload preview")}">
            ${removeAction ? `<button class="upload-preview-remove" type="button" onclick="${removeAction}(${index})" aria-label="Remove upload">✕</button>` : ""}
          </div>
          <div class="upload-preview-meta">${escapeHtml(item.name || `Image ${index + 1}`)}</div>
          <label class="sr-only" for="upload-alt-${index}">Image description ${index + 1}</label>
          <input
            class="form-input upload-preview-alt"
            id="upload-alt-${index}"
            type="text"
            maxlength="120"
            value="${escapeHtml(item.alt || "")}"
            placeholder="Short alt text / description"
            ${altAction ? `oninput="${altAction}(${index}, this.value)"` : ""}
          >
        </div>
      `).join("")}
    </div>
  `;
}

function mentionQueryAtCaret(text, selectionStart) {
  const before = String(text || "").slice(0, Math.max(0, Number(selectionStart || 0)));
  const match = before.match(/(^|\s)@([A-Za-z0-9_-]{1,24})$/);
  if (!match) return null;
  return {
    query: match[2],
    start: before.length - match[2].length - 1,
    end: before.length,
  };
}

function insertMentionAtCaret(textarea, username) {
  if (!textarea) return;
  const caret = textarea.selectionStart || 0;
  const token = mentionQueryAtCaret(textarea.value, caret);
  if (!token) return;
  const before = textarea.value.slice(0, token.start);
  const after = textarea.value.slice(token.end);
  const insertion = `@${username} `;
  textarea.value = `${before}${insertion}${after}`;
  const nextCaret = before.length + insertion.length;
  textarea.setSelectionRange(nextCaret, nextCaret);
  textarea.focus();
}

function queryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function replacePageQuery(params = {}) {
  const url = new URL(window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });
  window.history.replaceState({}, "", url);
}

function absoluteSiteUrl(path = "/") {
  return new URL(path, window.location.origin).toString();
}

function upsertMetaTag(selector, attributes) {
  let node = document.head.querySelector(selector);
  if (!node) {
    node = document.createElement("meta");
    Object.entries(attributes).forEach(([key, value]) => {
      if (key !== "content") {
        node.setAttribute(key, value);
      }
    });
    document.head.appendChild(node);
  }
  if (Object.prototype.hasOwnProperty.call(attributes, "content")) {
    node.setAttribute("content", attributes.content || "");
  }
  return node;
}

function upsertLinkTag(selector, attributes) {
  let node = document.head.querySelector(selector);
  if (!node) {
    node = document.createElement("link");
    Object.entries(attributes).forEach(([key, value]) => {
      if (key !== "href") {
        node.setAttribute(key, value);
      }
    });
    document.head.appendChild(node);
  }
  if (Object.prototype.hasOwnProperty.call(attributes, "href")) {
    node.setAttribute("href", attributes.href || "");
  }
  return node;
}

function setPageMetadata(options = {}) {
  const title = String(options.title || "OmniForum");
  const description = String(options.description || "OmniForum is a modern community forum for discussion, support, and direct messaging.");
  const canonicalPath = options.canonicalPath || `${window.location.pathname}${window.location.search}`;
  const canonicalUrl = absoluteSiteUrl(canonicalPath);
  const ogType = options.type || "website";
  const robots = options.noindex ? "noindex, nofollow" : "index, follow";
  document.title = title;
  upsertMetaTag('meta[name="description"]', { name: "description", content: description });
  upsertMetaTag('meta[property="og:site_name"]', { property: "og:site_name", content: "OmniForum" });
  upsertMetaTag('meta[property="og:title"]', { property: "og:title", content: title });
  upsertMetaTag('meta[property="og:description"]', { property: "og:description", content: description });
  upsertMetaTag('meta[property="og:type"]', { property: "og:type", content: ogType });
  upsertMetaTag('meta[property="og:url"]', { property: "og:url", content: canonicalUrl });
  upsertMetaTag('meta[name="twitter:card"]', { name: "twitter:card", content: options.imageUrl ? "summary_large_image" : "summary" });
  upsertMetaTag('meta[name="twitter:title"]', { name: "twitter:title", content: title });
  upsertMetaTag('meta[name="twitter:description"]', { name: "twitter:description", content: description });
  upsertMetaTag('meta[name="robots"]', { name: "robots", content: robots });
  if (options.imageUrl) {
    const imageUrl = absoluteSiteUrl(options.imageUrl);
    upsertMetaTag('meta[property="og:image"]', { property: "og:image", content: imageUrl });
    upsertMetaTag('meta[name="twitter:image"]', { name: "twitter:image", content: imageUrl });
  } else {
    document.head.querySelector('meta[property="og:image"]')?.remove();
    document.head.querySelector('meta[name="twitter:image"]')?.remove();
  }
  upsertLinkTag('link[rel="canonical"]', { rel: "canonical", href: canonicalUrl });
}

function paginationLabel(pagination) {
  if (!pagination) return "";
  const total = Number(pagination.totalItems || 0);
  const offset = Number(pagination.offset || 0);
  if (!total) return "0 results";
  const start = offset + 1;
  const end = Math.min(total, offset + Number(pagination.pageSize || 0));
  return `${start}-${end} of ${total}`;
}

function renderPaginationControls(pagination, handlers = {}) {
  if (!pagination || Number(pagination.totalPages || 1) <= 1) return "";
  const page = Number(pagination.page || 1);
  const totalPages = Number(pagination.totalPages || 1);
  const previousAction = handlers.previous || "";
  const nextAction = handlers.next || "";
  return `
    <div class="pagination-bar">
      <div class="pagination-copy">Page ${page} of ${totalPages} · ${escapeHtml(paginationLabel(pagination))}</div>
      <div class="pagination-actions">
        <button class="btn btn-ghost btn-sm" ${pagination.hasPrev ? `onclick="${previousAction}"` : "disabled"}>Previous</button>
        <button class="btn btn-ghost btn-sm" ${pagination.hasNext ? `onclick="${nextAction}"` : "disabled"}>Next</button>
      </div>
    </div>
  `;
}

function draftStorageKey(scope, id = "") {
  return `nexus:draft:${scope}:${id || "default"}`;
}

function loadDraft(scope, id = "") {
  try {
    const raw = window.localStorage.getItem(draftStorageKey(scope, id));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveDraft(scope, id = "", payload = {}) {
  try {
    window.localStorage.setItem(draftStorageKey(scope, id), JSON.stringify(payload));
  } catch {
    // Ignore localStorage failures.
  }
}

function clearDraft(scope, id = "") {
  try {
    window.localStorage.removeItem(draftStorageKey(scope, id));
  } catch {
    // Ignore localStorage failures.
  }
}

function listDrafts() {
  const prefix = "nexus:draft:";
  const drafts = [];
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key || !key.startsWith(prefix)) continue;
      const [, , scope, ...idParts] = key.split(":");
      const raw = window.localStorage.getItem(key);
      const payload = raw ? JSON.parse(raw) : {};
      const title = payload.title || payload.content || "";
      drafts.push({
        key,
        scope,
        id: idParts.join(":") || "default",
        savedAt: payload.savedAt || "",
        title: String(title || "Untitled draft").slice(0, 80),
        payload,
      });
    }
  } catch {
    return drafts;
  }
  return drafts.sort((a, b) => String(b.savedAt || "").localeCompare(String(a.savedAt || "")));
}

function serializeJsArg(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return `'${String(value ?? "")
    .replaceAll("\\", "\\\\")
    .replaceAll("'", "\\'")
    .replaceAll("\r", "\\r")
    .replaceAll("\n", "\\n")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029")}'`;
}

window.DB = DB;
window.SITE_THEMES = SITE_THEMES;
window.escapeHtml = escapeHtml;
window.fmtNum = fmtNum;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.formatRelativeTime = formatRelativeTime;
window.initialsForUser = initialsForUser;
window.applySiteTheme = applySiteTheme;
window.UPLOAD_LIMITS = UPLOAD_LIMITS;
window.ALLOWED_REACTIONS = ALLOWED_REACTIONS;
window.readImageUploads = readImageUploads;
window.readSingleImageUpload = readSingleImageUpload;
window.renderInlineMedia = renderInlineMedia;
window.renderUserContent = renderUserContent;
window.bindDropTarget = bindDropTarget;
window.bindPasteImageTarget = bindPasteImageTarget;
window.renderUploadPreviewList = renderUploadPreviewList;
window.mentionQueryAtCaret = mentionQueryAtCaret;
window.insertMentionAtCaret = insertMentionAtCaret;
window.toggleSensitiveMedia = toggleSensitiveMedia;
window.downloadJsonFile = downloadJsonFile;
window.downloadTextFile = downloadTextFile;
window.queryParam = queryParam;
window.replacePageQuery = replacePageQuery;
window.absoluteSiteUrl = absoluteSiteUrl;
window.setPageMetadata = setPageMetadata;
window.renderPaginationControls = renderPaginationControls;
window.loadDraft = loadDraft;
window.saveDraft = saveDraft;
window.clearDraft = clearDraft;
window.listDrafts = listDrafts;
window.serializeJsArg = serializeJsArg;

applyInitialSiteTheme();
