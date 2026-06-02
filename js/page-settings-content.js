/* Settings page main content renderer */

function renderSettingsContent() {
  const container = document.getElementById("settingsContent");
  if (!container) return;
  const user = Auth.getCurrentUser();
  document.title = "OmniForum — Settings";

  if (!user) {
    container.innerHTML = `
      <div class="page-section settings-guest-panel">
        <p class="hero-eyebrow">Account Center</p>
        <h1 class="thread-title">Sign in to manage your account</h1>
        <p class="muted-copy">Settings are only available to logged-in members. Once you sign in, this page becomes your account hub for profile edits, password changes, communication preferences, saved threads, sessions, and role-based tools.</p>
        <div class="settings-guest-actions">
          <button class="btn btn-primary" onclick="showLoginModal()">Log In</button>
          <button class="btn btn-ghost" onclick="showRegisterModal()">Create Account</button>
        </div>
      </div>
    `;
    return;
  }

  const role = DB.roles[user.role] || DB.roles.new;
  const xpData = DB.getXPForNextLevel(user.xp || 0);
  const progress = xpData.needed > 0 ? Math.min(100, Math.round((xpData.current / xpData.needed) * 100)) : 100;
  const moderation = user.moderation || null;
  const preferences = user.preferences || {
    siteTheme: "midnight",
    dmPrivacy: "everyone",
    notifyReplies: true,
    notifyLikes: true,
    notifyMentions: true,
    notifyDms: true,
  };
  const sessionAudit = user.recentSessions || user.sessionAudit || [];
  const library = user.library || { bookmarks: [], subscriptions: [] };
  const community = user.community || { signature: "", profileBadge: "", profileAccent: "" };
  const recovery = user.recovery || { discordUsername: "", codes: { active: 0, total: 0 } };
  const emailAuthEnabled = DB.isEmailAuthEnabled();
  const mediaUsage = user.mediaUsage || null;
  const relationships = user.relationships || [];

  const statusMarkup = moderation
    ? renderModerationStatus(moderation)
    : `
      <div class="moderation-status-stack">
        <div class="moderation-status-card ok settings-status-card">
          <div class="moderation-status-title">Account Clear</div>
          <div class="moderation-status-copy">There are no active restrictions on this account right now.</div>
        </div>
      </div>
    `;

  const staffSection = Auth.isStaff()
    ? `
      <div class="page-section">
        <div class="page-section-title">Staff Tools</div>
        <p class="muted-copy settings-section-copy">These controls are only visible to moderators and above.</p>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Reports Queue</div>
            <div class="settings-tool-copy">${fmtNum(user.reportCount || 0)} open user reports waiting for review.</div>
            <div class="stack-actions">
              <button class="btn btn-primary btn-sm" onclick="showReportsQueue()">Open Reports</button>
            </div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Staff Inbox</div>
            <div class="settings-tool-copy">${fmtNum(user.noticeCount || 0)} contact notices currently need staff attention.</div>
            <div class="stack-actions">
              <button class="btn btn-outline btn-sm" onclick="showStaffInbox()">Open Inbox</button>
            </div>
          </div>
        </div>
      </div>
    `
    : "";

  const adminSection = Auth.isAdmin()
    ? `
      <div class="page-section">
        <div class="page-section-title">Admin Controls</div>
        <p class="muted-copy settings-section-copy">Administrative tooling is intentionally hidden from moderators and below.</p>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Section Editor</div>
            <div class="settings-tool-copy">Create, reorder, and permission forum sections. This stays admin+ only.</div>
            <div class="stack-actions">
              <button class="btn btn-primary btn-sm" onclick="showSectionManager()">Manage Sections</button>
            </div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Admin Access</div>
            <div class="settings-tool-copy">You can moderate moderator-level accounts, issue recovery passwords, and manage section structure.</div>
          </div>
          <div class="settings-tool-card">
            <div class="settings-tool-title">Operations</div>
            <div class="settings-tool-copy">Backups, health signals, logs, and orphaned media cleanup stay admin+ only.</div>
            <div class="stack-actions">
              <button class="btn btn-outline btn-sm" onclick="showAdminOpsModal()">Open Operations</button>
            </div>
          </div>
        </div>
      </div>
    `
    : "";

  const ownerSection = Auth.isOwner()
    ? `
      <div class="page-section">
        <div class="page-section-title">Owner Notes</div>
        <div class="settings-tool-grid">
          <div class="settings-tool-card">
            <div class="settings-tool-title">Highest Permission Tier</div>
            <div class="settings-tool-copy">Owner-level access can manage admins, change owner-owned areas, and bypass normal admin ceilings. Keep this account especially secure.</div>
          </div>
        </div>
      </div>
    `
    : "";

  container.innerHTML = `
    <div class="page-section legal-hero">
      <p class="hero-eyebrow">Account Center</p>
      <h1 class="thread-title">Settings for ${escapeHtml(user.username)}</h1>
      <p class="muted-copy">Manage your profile, privacy, saved threads, sessions, account status, and any role-based tools from one place.</p>
    </div>

    <div class="page-section">
      <div class="page-section-title">Account Overview <span>${roleBadge(user.role)}</span></div>
      <div class="settings-stat-grid">
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.posts || 0)}</div>
          <div class="settings-stat-label">Posts</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.threads || 0)}</div>
          <div class="settings-stat-label">Threads</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.xp || 0)}</div>
          <div class="settings-stat-label">XP</div>
        </div>
        <div class="settings-stat-card">
          <div class="settings-stat-value">${fmtNum(user.likesReceived || 0)}</div>
          <div class="settings-stat-label">Likes Received</div>
        </div>
      </div>
      <div class="xp-bar-wrap mt-18">
        <div class="xp-label">
          <span>${escapeHtml(xpData.label)} Progress</span>
          <span>${progress}%</span>
        </div>
        <progress class="xp-progress" value="${progress}" max="100"></progress>
      </div>
      <div class="detail-list">
        <div><span>Role</span><strong>${escapeHtml(role.label)}</strong></div>
        <div><span>Member Since</span><strong>${escapeHtml(formatDate(user.joined))}</strong></div>
        <div><span>Trust Level</span><strong>${escapeHtml(user.trust?.label || "Member")}</strong></div>
        <div><span>Status</span><strong>${user.online ? "Online" : "Offline"}</strong></div>
        <div><span>Restrictions</span><strong>${escapeHtml(settingsRestrictionLabel(user))}</strong></div>
        ${user.trust?.limits ? `<div><span>Posting Limits</span><strong>${escapeHtml(user.trust.limits)}</strong></div>` : ""}
        <div><span>Unread Alerts</span><strong>${fmtNum(user.notificationCount || 0)}</strong></div>
        <div><span>Unread Messages</span><strong>${fmtNum(user.messageCount || 0)}</strong></div>
        ${mediaUsage ? `<div><span>Media Used</span><strong>${escapeHtml(mediaUsage.bytesLabel || "0B")}</strong></div>` : ""}
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Profile</div>
      <p class="muted-copy settings-section-copy">Update the public details other members see when they open your profile.</p>
      <div class="form-error" id="settingsProfileError"></div>
      <div class="settings-profile-shell">
        <div class="settings-avatar-panel">
          ${makeAvatar(user, "settings")}
          <div class="tiny-copy">Visible in posts, member cards, DMs, and the leaderboard.</div>
        </div>
        <div class="settings-form-grid">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input class="form-input" id="settingsUsername" maxlength="24" value="${escapeHtml(user.username || "")}" placeholder="Username">
            <div class="form-hint">3-24 characters using letters, numbers, _ or -.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <input class="form-input" value="${escapeHtml(role.label)}" disabled>
            <div class="form-hint">Role changes stay staff-controlled.</div>
          </div>
          ${emailAuthEnabled ? `
            <div class="form-group full">
              <label class="form-label">Recovery Email</label>
              <input class="form-input" id="settingsEmail" type="email" maxlength="200" value="${escapeHtml(user.email || "")}" placeholder="you@example.com" autocomplete="email">
              <div class="form-hint">Optional. Used only for email password reset when the operator has enabled email auth.</div>
            </div>
          ` : ""}
          <div class="form-group full">
            <label class="form-label">Profile Picture</label>
            <input class="form-input" id="settingsAvatarInput" type="file" accept="image/png,image/jpeg,image/gif,image/webp">
            <div class="form-hint">PNG, JPG, GIF, or WEBP. Keep it under ${Math.round(UPLOAD_LIMITS.avatarBytes / (1024 * 1024))}MB.</div>
            ${user.avatarUrl ? `
              <label class="checkbox-row settings-checkbox-row">
                <input type="checkbox" id="settingsRemoveAvatar">
                <span>Remove the current profile picture</span>
              </label>
            ` : ""}
          </div>
          <div class="form-group full">
            <label class="form-label">Bio</label>
            <textarea class="form-textarea" id="settingsBio" maxlength="280" placeholder="Tell the forum a little about yourself.">${escapeHtml(user.bio || "")}</textarea>
            <div class="form-hint">Up to 280 characters.</div>
          </div>
          <div class="form-group full">
            <label class="form-label">Status Message</label>
            <input class="form-input" id="settingsStatusText" maxlength="120" value="${escapeHtml(community.statusText || "")}" placeholder="Working on a new project, open to DMs, heads down in support mode...">
            <div class="form-hint">A short public line shown on your profile and member cards.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Profile Badge</label>
            <input class="form-input" id="settingsProfileBadge" maxlength="32" value="${escapeHtml(community.profileBadge || "")}" placeholder="Builder">
            <div class="form-hint">Optional short badge shown on your profile.</div>
          </div>
          <div class="form-group">
            <label class="form-label">Accent Color</label>
            <select class="form-input" id="settingsProfileAccent">${accentOptionMarkup(community.profileAccent || "")}</select>
            <div class="form-hint">A subtle accent used on your profile card.</div>
          </div>
          <div class="form-group full">
            <label class="form-label">Signature</label>
            <textarea class="form-textarea" id="settingsSignature" maxlength="240" placeholder="Appears below your posts. Supports the same markdown / BBCode as the post composer.">${escapeHtml(community.signature || "")}</textarea>
            <div class="form-hint">Great for a short intro, favorite quote, or project link.</div>
          </div>
          <div class="form-group full">
            <label class="form-label">Recovery Discord Username</label>
            <input class="form-input" id="settingsRecoveryDiscord" maxlength="64" value="${escapeHtml(recovery.discordUsername || "")}" placeholder="your.discord.username">
            <div class="form-hint">Optional. Admins can use this as a verification note if you ever need email-free account recovery.</div>
          </div>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-outline" onclick="showProfile(${JSON.stringify(user.id)})">Preview Profile</button>
        <button class="btn btn-primary" onclick="saveSettingsProfile()">Save Profile</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Appearance</div>
      <p class="muted-copy settings-section-copy">Choose a full-site color scheme. Clicking an option previews it immediately; saving makes it your default on every page.</p>
      <div class="form-error" id="settingsThemeError"></div>
      <div class="settings-theme-grid">
        ${siteThemeOptionMarkup(preferences.siteTheme || "midnight")}
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsTheme()">Save Theme</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Communication & Privacy</div>
      <p class="muted-copy settings-section-copy">Decide who can start DMs with you and which activity creates alerts.</p>
      <div class="form-error" id="settingsPreferencesError"></div>
      <div class="settings-form-grid">
        <div class="form-group full">
          <label class="form-label">Direct Message Privacy</label>
          <select class="form-input" id="settingsDmPrivacy">
            <option value="everyone"${preferences.dmPrivacy === "everyone" ? " selected" : ""}>Everyone</option>
            <option value="members"${preferences.dmPrivacy === "members" ? " selected" : ""}>Members and Above</option>
            <option value="staff_only"${preferences.dmPrivacy === "staff_only" ? " selected" : ""}>Staff Only</option>
            <option value="disabled"${preferences.dmPrivacy === "disabled" ? " selected" : ""}>Disable Member DMs</option>
          </select>
          <div class="form-hint">Staff can still reach you for moderation or safety reasons.</div>
        </div>
        <div class="form-group full">
          <label class="form-label">Notification Preferences</label>
          <div class="checkbox-stack">
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyReplies"${preferences.notifyReplies ? " checked" : ""}> <span>Replies in threads you participate in or follow</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyLikes"${preferences.notifyLikes ? " checked" : ""}> <span>Likes on your posts</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyMentions"${preferences.notifyMentions ? " checked" : ""}> <span>@mentions</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsNotifyDms"${preferences.notifyDms ? " checked" : ""}> <span>Direct messages</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsBlurSensitiveMedia"${preferences.blurSensitiveMedia !== false ? " checked" : ""}> <span>Blur media marked sensitive until I reveal it</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsCompactPostLayout"${preferences.compactPostLayout ? " checked" : ""}> <span>Use the compact thread layout when available</span></label>
            <label class="checkbox-row"><input type="checkbox" id="settingsHideIgnoredContent"${preferences.hideIgnoredContent !== false ? " checked" : ""}> <span>Hide posts from members I ignore</span></label>
          </div>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsPreferences()">Save Preferences</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Saved Threads & Following</div>
      <p class="muted-copy settings-section-copy">Bookmarks are private. Followed threads continue to send reply alerts when your preferences allow it.</p>
      <div class="settings-library-grid">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Bookmarked Threads</div>
          <div class="settings-tool-copy">${fmtNum(library.bookmarks?.length || 0)} recent saved thread${(library.bookmarks?.length || 0) === 1 ? "" : "s"}.</div>
          ${renderSavedThreads(library.bookmarks || [], "You have not bookmarked any threads yet.")}
        </div>
        <div class="settings-tool-card">
          <div class="settings-tool-title">Followed Threads</div>
          <div class="settings-tool-copy">${fmtNum(library.subscriptions?.length || 0)} recent followed thread${(library.subscriptions?.length || 0) === 1 ? "" : "s"}.</div>
          ${renderSavedThreads(library.subscriptions || [], "You are not following any threads yet.")}
        </div>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Draft Recovery</div>
      <p class="muted-copy settings-section-copy">Drafts are saved locally in this browser while you write threads and replies, with separate drafts per section or thread.</p>
      ${renderDraftRecoveryList()}
    </div>

    <div class="page-section">
      <div class="page-section-title">Ignored & Blocked Members</div>
      <p class="muted-copy settings-section-copy">Manage the people whose posts you hide or whose DMs you block.</p>
      ${renderRelationshipList(relationships)}
    </div>

    <div class="page-section">
      <div class="page-section-title">Security</div>
      <p class="muted-copy settings-section-copy">Use a strong password you do not reuse anywhere else.</p>
      <div class="form-error" id="settingsPasswordError"></div>
      ${user.mustResetPassword ? `
        <div class="moderation-status-card info settings-status-card">
          <div class="moderation-status-title">Password Reset Required</div>
          <div class="moderation-status-copy">This account is currently using a temporary password. Set a new permanent one here before continuing normal forum use.</div>
        </div>
      ` : ""}
      <div class="settings-form-grid">
        ${user.mustResetPassword ? "" : `
          <div class="form-group">
            <label class="form-label">Current Password</label>
            <input class="form-input" id="settingsCurrentPassword" type="password" autocomplete="current-password" placeholder="Current password">
          </div>
        `}
        <div class="form-group">
          <label class="form-label">New Password</label>
          <input class="form-input" id="settingsNewPassword" type="password" autocomplete="new-password" placeholder="New password">
        </div>
        <div class="form-group">
          <label class="form-label">Confirm New Password</label>
          <input class="form-input" id="settingsConfirmPassword" type="password" autocomplete="new-password" placeholder="Confirm new password">
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveSettingsPassword()">Update Password</button>
      </div>
      <div class="settings-tool-grid mt-18">
        <div class="settings-tool-card">
          <div class="settings-tool-title">Recovery Codes</div>
          <div class="settings-tool-copy">One-time codes let you recover the account without email, then force a password reset.</div>
          <div class="detail-list">
            <div><span>Active Codes</span><strong>${fmtNum(recovery.codes?.active || 0)}</strong></div>
            <div><span>Last Generated</span><strong>${escapeHtml(formatDateTime(recovery.codes?.latestCreatedAt))}</strong></div>
          </div>
          <div class="form-actions">
            <button class="btn btn-outline btn-sm" onclick="showRecoveryCodesModal()">Manage Codes</button>
          </div>
        </div>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Sessions</div>
      <p class="muted-copy settings-section-copy">Review the latest places this account was active and sign out any other sessions.</p>
      <div class="form-error" id="settingsSessionsError"></div>
      ${renderSessionList(sessionAudit)}
      <div class="form-actions">
        <button class="btn btn-outline" onclick="revokeSettingsSessions()">Sign Out Other Sessions</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Account Status</div>
      <p class="muted-copy settings-section-copy">If staff actions affect your account, they will surface here.</p>
      ${statusMarkup}
    </div>

    ${(user.appeals?.length || moderation?.isBanned || moderation?.isTimedOut || moderation?.isMuted) ? `
      <div class="page-section">
        <div class="page-section-title">Appeals</div>
        <p class="muted-copy settings-section-copy">Use appeals for bans, timeouts, or mutes that you believe should be reviewed.</p>
        <div class="form-actions">
          <button class="btn btn-primary" onclick="showAppealsQueue('all')">Open Appeals</button>
        </div>
        ${renderAppealList(user.appeals || [])}
      </div>
    ` : ""}

    ${staffSection}
    ${adminSection}
    ${ownerSection}

    <div class="page-section">
      <div class="page-section-title">Account Data</div>
      <p class="muted-copy settings-section-copy">Download a JSON export of your profile, posts, messages, relationships, and account metadata.</p>
      ${mediaUsage ? `
        <div class="detail-list">
          <div><span>Media Library</span><strong>${escapeHtml(mediaUsage.bytesLabel || "0B")} / ${escapeHtml(mediaUsage.limitBytesLabel || "0B")}</strong></div>
          <div><span>Files</span><strong>${fmtNum(mediaUsage.files || 0)} / ${fmtNum(mediaUsage.limitFiles || 0)}</strong></div>
          <div><span>Remaining</span><strong>${escapeHtml(mediaUsage.remainingBytesLabel || "0B")}</strong></div>
          <div><span>Uploads</span><strong>${fmtNum(mediaUsage.postMediaCount || 0)} post media</strong></div>
        </div>
      ` : ""}
      <div class="form-actions">
        <button class="btn btn-primary" onclick="exportSettingsData()">Download My Data</button>
      </div>
    </div>

    <div class="page-section">
      <div class="page-section-title">Policy & Help</div>
      <div class="settings-link-grid">
        <div class="settings-link-card">
          <a href="rules.html">Forum Rules</a>
          <div class="settings-tool-copy">Review the community standards that govern posting and moderation.</div>
        </div>
        <div class="settings-link-card">
          <a href="privacy.html">Privacy Policy</a>
          <div class="settings-tool-copy">See what the forum stores, how sessions work, and what staff can review.</div>
        </div>
        <div class="settings-link-card">
          <a href="contact.html">Contact Staff</a>
          <div class="settings-tool-copy">Reach moderators/admins for support, account issues, or policy questions.</div>
        </div>
      </div>
    </div>
  `;
}
