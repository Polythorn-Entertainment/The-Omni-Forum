# OmniForum Features

## Forum And Community

- Category/section forum layout
- Threads and replies
- Post quoting
- Rich post formatting with markdown-style and BBCode-style content
- Image/GIF uploads in new threads and replies
- Server-side media processing with resize/compression, metadata stripping, and generated thumbnails
- Polls inside threads
- Saved threads and thread follows
- Related threads and trending threads
- Featured threads and community spotlight surfaces
- Search across content
- Optional SQLite FTS5-backed search index with LIKE fallback

## Accounts And Profiles

- Registration and login
- Invite-only registration, admin approval review, throttling, and blocked username patterns
- Persistent cookie sessions
- Profile pictures
- Signatures
- Profile badge and accent customization
- Saved site theme preference in Settings
- Password change and temporary-password reset flow
- One-time recovery codes for email-free account recovery
- Optional recovery Discord username for admin verification notes
- Session review and sign-out-other-sessions tools
- DM privacy and notification preferences
- Draft recovery for locally saved thread and reply drafts
- Account data export from Settings
- Ignored-content and blocked-DM member controls
- Sensitive-media, compact-layout, and ignored-content presentation toggles

## Appearance And Personalization

- Full-site theme switching from Settings
- 15 preset color schemes built into the forum
- Live theme preview before saving
- Theme preference saved per account and re-applied after login/refresh
- Admin branding editor for site name, logo text/mark, hero copy, footer links, SEO defaults, policy intros, upload policy, feature toggles, and default theme

## Messaging And Alerts

- Direct messages
- Unread counts
- Filtered notifications for replies, likes, mentions, DMs, reports, appeals, contact notices, signups, and staff actions
- Live updates over Server-Sent Events for alerts, section activity, and thread replies

## Moderation And Staff Tools

- Reports queue
- Appeals queue
- Staff inbox for contact form submissions
- Saved moderation macros for consistent report triage notes
- Report internal discussion notes, private staff assignments, SLA labels, and escalation tracking
- Warnings, notes, XP adjustments, timeouts, bans, mutes, and shadow mutes
- Role changes with audit history
- Thread moderation, lock/pin/feature/solve controls, split/merge/move tools, staff-only thread notes, and section permissions
- Moderation analytics in Operations
- Trash/recovery view for soft-deleted threads and replies
- Optional Discord webhook notifications for new staff-facing events

## Admin Operations

- Signup Controls for public/open, invite-only, closed, and approval-queue registration modes
- First-run setup wizard for site name, branding, policy copy, registration mode, section layout, theme default, and first backup
- Admin import/export tools for users, threads, posts, reports, moderation logs, and settings as JSON/CSV with no-write import previews
- Backup archive creation
- Downloadable backup inventory in Operations
- Guided restore checklist and copyable restore command in Operations
- Production health dashboard with database size, media usage, backup status, latest errors, queue counts, plugin status, onboarding checklist, production install checks, analytics, and recovery readiness
- Searchable Audit Log in Operations for moderation, signup, content, section, plugin, and operations actions
- Runtime logs view
- Orphaned media cleanup
- Section management
- Plugin enable/disable controls with manifest-declared asset loading rules
- Recovery/restore controls for soft-deleted content

## Roles

- `Owner`: first registered account, full control
- `Admin`: full site administration and operations access
- `Mod`: moderation tools, staff inbox, report/appeal handling
- `Veteran`, `Member`, `New`: community roles used for section read/write permissioning

Sections can be hidden entirely from users who do not meet the section read role.

## Recovery And Contact

- Email account features are disabled by default. Set `OMNIFORUM_EMAIL_AUTH_ENABLED=1` and SMTP env vars to reveal optional recovery email fields and password reset links.
- Admins and the owner can issue a temporary password for account recovery.
- Temporary passwords expire, force the user to reset their password after login, and create an audit trail.
- Users can generate one-time recovery codes from Settings and use them from the login form if they forget their password.
- Users can save a Discord username in Settings for admin verification notes.
- The contact form supports an optional Discord username so staff have an off-site handle to reference.

## Operations Surfaces

- Runtime logs: `data/logs/server.log`, `data/logs/access.log`, and `data/logs/app.jsonl`
- First-run setup wizard: `Settings -> Operations -> Setup Wizard`
- Import/export and preview tools: `Settings -> Operations -> Import / Export`
- Staff workflow macros: `Settings -> Operations -> Staff Workflows`
- Media cleanup: `Settings -> Operations -> Media Cleanup`
- Backups: `data/exports/backups/`
- Private uploads: `data/uploads/`
