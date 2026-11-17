# Allsafe AiTM Awareness Lab

An educational, local-only demonstration of an **Adversary-in-the-Middle (AiTM) credential relay**, built for red-teaming / security-awareness lectures. The fictional company is inspired by *Mr. Robot*. Allsafe names and imagery are third-party references, not official assets or licensed by the project.

> **For isolated classroom use only.** This lab contains a working credential-relay proxy. Do not point it at anything other than its own bundled demo app, do not expose it beyond `127.0.0.1`, and do not reuse any part of it against a real login page or real users.

## What it demonstrates

1. A student (playing "the victim") is told the one demo account that exists in this lab (`DEMO_EMAIL` / `DEMO_PASSWORD`).
2. They open the **phishing** page (`http://127.0.0.1:8082`) — a pixel clone of the real login page — and type those credentials in.
3. The clone's `relay` service replays those exact credentials against the **real** app's real `/login` endpoint, over a Docker network the victim never sees.
4. The real app authenticates the relay as if it were a normal browser and issues a real session cookie.
5. The relay **exfiltrates** that cookie — persists it to the `loot_data` volume and logs it in full — before grafting the same cookie onto the victim's own browser and redirecting it straight to `http://127.0.0.1:8081/workspace`. The victim lands on the **real, legitimate workspace, already logged in**, having never actually talked to it directly; meanwhile the attacker already has a standing copy of that same session.
6. `scripts/monitor.py` surfaces the stolen token live, in a Rich table, the moment it's captured — ready to copy into the follow-up lesson.

The credentials are relayed as typed, not hard-coded — this is what a real AiTM phishing kit (e.g. Evilginx-style) does to bypass "just check the URL" advice and even static-password MFA. A good discussion point for the class: the only thing that made step 5 "just work" is that both sites share the same host (`127.0.0.1`) — browsers scope cookies by domain, **not by port**, so a session cookie set while visiting port `8082` is also sent to port `8081`. That's a deliberate simplification to keep the lab self-contained on one machine; real AiTM kits instead rely on a look-alike *domain* and a TLS cert, and steal the session cookie directly rather than depending on a port quirk.

## Architecture

- **`legitimate/`** — Real Flask login, server-side PostgreSQL session records, Nginx reverse proxy and a protected workspace. Login, workspace and logout are real routes of the same corporate service, with CSRF-protected forms and `httponly`/`SameSite=Strict` session cookies.
- **`phishing/`** — A static visual clone of the login page, served by Nginx, plus a `relay` service that performs the actual credential relay described above.
- **`scripts/`** — Central CLI start/stop/reset and a read-only Rich monitor that tails both the legitimate app's auth events and the relay's capture/relay events side by side.

**Network isolation:**
- `legitimate/` and `phishing/` each still define their own `internal: true` Docker network for their own containers (database, app, nginx) — fully isolated from the host's internet. Each stack also has a small, non-internal `*_front` network used only by its Nginx container, purely so the host-published port works (an `internal: true` network has no NAT route in either direction, including inbound from the host) — app and db never touch it.
- A single additional network, `aitm-relay-net` (also `internal: true`, so it never reaches the host's internet either), is shared between the two stacks. It is the **only** path between them: just `legitimate`'s Nginx container (reachable as `legitimate-gateway`) and `phishing`'s `relay` container attach to it. This is the "wire" the AiTM relay runs over, kept deliberately visible and minimal for teaching.
- Host ports bind to `127.0.0.1` only.

## Running it

```bash
cp .env.example .env        # first run only
scripts/start.sh            # brings up both stacks + the shared relay network
scripts/monitor.py          # optional: live event timeline for the class
```

- Real app: `http://127.0.0.1:8081` (log in with the demo account directly, to show the "normal" flow first)
- Phishing clone: `http://127.0.0.1:8082` (log in here to show the relay)

```bash
scripts/stop.sh [legitimate | phishing | all]
scripts/reset.sh            # wipes the legitimate DB/sessions and restarts it
```

Sessions expire after `SESSION_TTL_MINUTES` (45 by default). If a demo run sits too long before you get to the Burp follow-up, the stolen token will have expired server-side — just submit the demo credentials on the phishing clone again to mint a fresh one.

## Follow-up lesson: replaying the stolen token in Burp Suite

Every successful relay persists the exfiltrated cookies to a named Docker volume (`loot_data`), independent of the live demo's terminal session, so you can come back to it in the next lesson:

```bash
scripts/loot.sh             # dumps every captured session as JSON
```

Each record has a `replay_header` (the literal `Cookie:` header value) and a `replay_url` (the real app's `/workspace`). Use the **most recent** record — sessions expire after `SESSION_TTL_MINUTES` (45 by default), so a token captured too long before the Burp lesson will already be dead server-side; if so, just submit the demo credentials on the phishing clone again right before the lesson to mint a fresh one. In Burp Suite:

1. Send a `GET /workspace` request to `http://127.0.0.1:8081` to Repeater.
2. Replace its `Cookie` header with the captured `replay_header` value.
3. Send it — no credentials, no login step, just the stolen `sid` — and get back the real, authenticated workspace. That's the session hijack, made visible.
