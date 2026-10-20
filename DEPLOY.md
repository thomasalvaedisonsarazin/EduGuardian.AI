# Putting EduGuardian AI online

This guide puts the app on the internet at `https://<your-domain>`, with HTTPS, daily backups
and a demo school that resets itself every day. It assumes **synthetic demo data only**: do not
load real student data until the privacy steps at the end are done.

What runs on the server (all in Docker):

| Service | Job |
|---|---|
| `caddy` | The only thing open to the internet (ports 80/443). Gets the HTTPS certificate automatically. Sends `/api/*` to the backend and everything else to the website. |
| `frontend` | The website (React, served by nginx). |
| `backend` | The API and the AI agents. |
| `db` | PostgreSQL. Not reachable from the internet. |
| `backup` | Dumps the database to `./backups` once a day, keeps 14 days. |
| `demo-reset` | Re-creates the demo school once a day, so visitors always see a clean demo. |

## 1. Buy a server and a domain

- **Server (VPS):** Ubuntu 24.04, at least **2 vCPU / 4 GB RAM / 40 GB disk** (e.g. Hetzner CX22,
  DigitalOcean 4 GB droplet, Hostinger KVM 2). Note its **public IP address**.
- **Domain:** any registrar. In its **DNS settings** add an **A record**: name `@`, value = the
  server's IP. (Optional: a second A record `www` with the same IP.) DNS can take up to an hour.

## 2. Prepare the server (once)

Log in from your computer: `ssh root@<server-ip>`, then:

```bash
# Docker + Compose plugin
curl -fsSL https://get.docker.com | sh

# Firewall: only SSH and web traffic
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable

# Get the code
git clone https://github.com/thomasalvaedisonsarazin/EduGuardian.AI.git /opt/eduguardian
cd /opt/eduguardian
```

## 3. Configure

```bash
cp .env.production.example .env
nano .env
```

Fill in every `<...>` value:

- `DOMAIN` and `ALLOWED_ORIGINS`: your domain, e.g. `eduguardian.in` and `["https://eduguardian.in"]`.
- `POSTGRES_PASSWORD`: run `openssl rand -base64 24` and paste the result.
- `SECRET_KEY`: run `openssl rand -base64 48` and paste the result. The app refuses to start
  with a weak key.
- `OPENAI_API_KEY`: your key. **Also set a monthly limit in your OpenAI account**
  (https://platform.openai.com/settings/organization/limits) as a second safety net.

Save with `Ctrl+O`, `Enter`, exit with `Ctrl+X`.

## 4. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend python -m app.seed      # create the demo school (first time only)
```

Open `https://<your-domain>` and log in with `demo@eduguardian.test` / `Demo@12345`.

## Everyday tasks

All commands run in `/opt/eduguardian` on the server. `P="-f docker-compose.yml -f docker-compose.prod.yml"`
saves typing: then use `docker compose $P ...`.

| Task | Command |
|---|---|
| Is everything running? | `docker compose $P ps` |
| See errors | `docker compose $P logs --tail 100 backend` |
| Update to the latest code | `git pull && docker compose $P up -d --build` |
| Reset the demo now | `docker compose exec backend python -m app.seed --reset` |
| List backups | `ls -lh backups/` |
| Restore a backup | `gunzip -c backups/<file>.sql.gz \| docker compose exec -T db psql -U edu -d eduguardian` (into an empty database) |

Copy backups off the server now and then (e.g. `scp root@<server-ip>:/opt/eduguardian/backups/* .`):
a backup on the same disk does not survive the server being lost.

## Safety settings that matter

- `ALLOW_REGISTRATION=false`: nobody can create new schools; only the demo accounts work.
  Without this, strangers could create schools and spend your OpenAI credit.
- `LLM_GLOBAL_MONTHLY_BUDGET_USD`: total AI spend per month across the whole server. When it is
  reached, plans fall back to templates (no AI) until next month.
- The demo password is public (it is in the README). That is fine **only** because the data is
  synthetic and is wiped every day.

## Before using real student data

Real marks are personal data of children. Before a pilot:

1. Written agreement with the school (what data, why, how long it is kept, who can see it).
2. A privacy policy page, and compliance with the applicable law (India: DPDP Act 2023; UAE: PDPL).
3. Turn off the demo: remove `demo` from `COMPOSE_PROFILES`, and change the demo account passwords.
4. Server in an appropriate region; off-server encrypted backups; tested restore.
5. Remaining review items in README "Known follow-ups".
