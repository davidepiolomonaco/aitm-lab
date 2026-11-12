# Allsafe AiTM Awareness Lab — isolated environments

An educational, demonstration with two completely independent Docker Compose projects. The fictional company is inspired by *Mr. Robot*. Allsafe names and imagery are third-party references, not official assets or licensed by the project.

## Architecture

- **`legitimate/`** — Real Flask login, server-side PostgreSQL session records, Nginx reverse proxy and protected workspace. Login and workspace are routes of the same corporate service.
- **`simulation/`** — A separately deployed static visual login replica served by Nginx;
- **`scripts/`** — Central CLI start/stop/reset and a read-only Rich monitor of redacted legitimate-app events.

**Network isolation:** each Compose file defines its own `internal: true` Docker network. The projects have no shared Docker network or backend calls. Host ports bind to `127.0.0.1` only.

