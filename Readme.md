# AppCTL — Service Orchestration & Monitoring

Dark-industrial dashboard for managing, monitoring, and controlling services running on any IP/host.

## Features

| Feature | Detail |
|---|---|
| **Health Monitoring** | HTTP health check every 30s (configurable) |
| **Downtime Alerts** | Email alert after 5 min of downtime (configurable) |
| **Recovery Alerts** | Automatic recovery notification email |
| **Start / Stop** | SSH command execution on remote/local hosts |
| **App Registry** | Register any app by URL or IP |
| **Live Updates** | WebSocket push — no polling in browser |
| **Incident Log** | Full downtime history with duration |

---

## Quick Start (Docker)

```bash
git clone <repo>
cd appctl

# Copy and configure env
cp .env.example backend/.env
# edit backend/.env — at minimum set SMTP_* for email alerts

docker compose up -d
```

Open http://localhost:8000

---

## Manual Setup

### 1. PostgreSQL

```bash
createdb appctl
createuser appctl -P  # set password: appctl
psql -c "GRANT ALL ON DATABASE appctl TO appctl;"
```

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp ../sample-env.txt .env   # edit with your values

uvicorn main:app --reload --port 8000
```

The frontend is served at http://localhost:8000 automatically.

---

## App Registration

When registering an app you need to provide:

| Field | Required | Example |
|---|---|---|
| Name | ✓ | `payment-api` |
| URL | ✓ | `http://10.0.1.15:3000` |
| Health Path | | `/health` (default `/`) |
| SSH Host | optional | `10.0.1.15` |
| SSH User | optional | `ubuntu` |
| SSH Key Path | optional | `/home/ubuntu/.ssh/id_rsa` |
| Start Command | optional | `cd /opt/app && ./start.sh` |
| Stop Command | optional | `pkill -f myapp` |

> SSH keys must be accessible **from the machine running AppCTL**, not the browser.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/apps` | List all registered apps |
| POST | `/api/apps` | Register new app |
| PATCH | `/api/apps/{id}` | Update app config |
| DELETE | `/api/apps/{id}` | Deregister app |
| POST | `/api/apps/{id}/start` | Start via SSH |
| POST | `/api/apps/{id}/stop` | Stop via SSH |
| POST | `/api/apps/{id}/check` | Force health check |
| GET | `/api/incidents` | All incidents |
| GET | `/api/stats` | Summary stats |
| WS | `/ws` | Real-time status stream |

Full interactive docs: http://localhost:8000/docs

---

## Email Alert Config

Uses SMTP with STARTTLS. Gmail App Passwords work out of the box:

1. Enable 2FA on Google account  
2. Go to https://myaccount.google.com/apppasswords  
3. Create a password for "Mail"  
4. Set `SMTP_PASSWORD` to the 16-char password  

---

## Architecture

```
browser ←─── WebSocket (live push) ───→ FastAPI
              REST API              ←→ SQLAlchemy → PostgreSQL
                                   ←→ APScheduler (health loop)
                                   ←→ Paramiko (SSH start/stop)
                                   ←→ smtplib (email alerts)
```
"# app-ctl" 
