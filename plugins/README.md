OmniForum plugins live in subdirectories of `/plugins`.

Each plugin directory needs a `plugin.json` manifest. Example:

```json
{
  "id": "example-tools",
  "name": "Example Tools",
  "version": "1.0.0",
  "description": "Adds small client-side enhancements.",
  "enabled": true,
  "author": "OmniForum",
  "client": {
    "styles": ["client/example.css"],
    "scripts": ["client/example.js"],
    "assets": ["client/example-icon.svg"]
  }
}
```

Loading rules:

- Only enabled plugins are served to the browser.
- Only files declared in `client.styles`, `client.scripts`, or `client.assets` are publicly served.
- Client assets must stay inside that plugin directory.
- Supported served extensions are CSS, JS, JSON, TXT, SVG, PNG, JPG, GIF, WEBP, WOFF, and WOFF2.

Admins can enable or disable installed plugins from the OmniForum Operations modal.
