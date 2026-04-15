Runtime forum data lives in this folder.

Files are created automatically when the site starts:

- `users.db` for accounts, roles, moderation state, password recovery flags, DM privacy, and notification preferences
- `sessions.db` for login sessions plus recent session/IP/user-agent audit metadata
- `sections.db` for forum categories and sections
- `threads.db` for thread records, bookmarks, and thread subscriptions
- `posts.db` for posts, likes, inline media, and post edit history
- `messages.db` for direct-message conversations
- `notifications.db` for alerts, mentions, likes, and staff-action notices
- `reports.db` for user-submitted reports, appeals, and moderation queue state
- `contact.db` for contact-form submissions, optional Discord usernames, and staff inbox review state

Uploaded forum media is stored under:

- `uploads/avatars/` for profile pictures
- `uploads/posts/` for inline thread and reply images/GIFs

Operational runtime files are also created here:

- `exports/backups/` for admin-created backup archives
- `logs/server.log` for the lightweight request / operations log

Those uploads are served through `/media/...` routes. The rest of `data/` remains private application storage.

Fresh reset behavior:

- If you stop the server and remove the `*.db` files in `data/`, OmniForum will recreate them automatically on the next `python3 app.py` start
- Default forum categories and sections are seeded again on startup
- Removing files under `uploads/`, `exports/backups/`, and `logs/server.log` clears user-generated media, backups, and the lightweight runtime log
