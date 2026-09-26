# Deployment Guide: Proxmox VE (LXC / VM) & Self-Hosting

This document details spinning up the Progressive Overload & AI Nutrition Workout PWA inside an unprivileged LXC container or VM on **Proxmox VE**, setting up persistent storage, and satisfying mobile PWA HTTPS requirements.

---

## 1. Prerequisites on Proxmox VE

You can deploy using either:
- **Option A (Recommended for low footprint)**: An unprivileged Debian 12 / Ubuntu 24.04 **LXC Container** with Docker enabled.
- **Option B**: A lightweight Alpine / Debian **Virtual Machine (VM)**.

### Proxmox LXC Container Preparation
If using an LXC container:
1. In the Proxmox Web GUI, create an LXC container (e.g., Ubuntu 22.04 or Debian 12, 1-2 vCPUs, 1024MB RAM, 8GB Disk).
2. Under **Container Options**:
   - Enable **Nesting**: `Yes` (Required for Docker inside LXC).
   - Under `Features`: check `keyctl=1` and `nesting=1`.
3. Start the LXC container and install Docker & Docker Compose:
   ```bash
   apt update && apt install -y curl git ca-certificates
   curl -fsSL https://get.docker.com | sh
   apt install -y docker-compose-plugin
   ```

---

## 2. Deploying the Workout App

### Step 1: Clone Repository & Configure Environment
Inside your container or VM terminal:
```bash
git clone <your-repo-url> /opt/workout-app
cd /opt/workout-app
```

Copy the environment template (if you wish to customize port or secrets):
```bash
cp .env.example .env
```
Key variables in `.env`:
- `HOST_PORT=8085` *(or any custom port of choice)*
- `OLLAMA_URL=http://<ollama-ip-or-host>:11434`
- `SPARKY_URL=http://<sparky-ip-or-host>:8080`
- `DEFAULT_OLLAMA_MODEL=qwen3:14b`
- `SPARKY_API_TOKEN=<your_sparky_token>`

### Step 2: Build and Start Containers
```bash
docker compose up -d --build
```

Verify service health:
```bash
docker compose ps
docker compose logs -f workout-app
```
You should see:
```text
Serving Workout PWA & API on http://0.0.0.0:8000
```
Database tables and the default `selected_ollama_model = qwen3:14b` setting are automatically migrated on container boot into the persistent volume `workout_app_data` (`/app/data/workout_app.db`).

---

## 3. Local Network Access & PWA HTTPS Setup

> [!IMPORTANT]
> **Mobile PWA Requirement**: Service Workers, PWA installation, and Web App Manifests require a secure context (**`HTTPS`**) on iOS Safari and Android Chrome (except on `localhost`).

To enable seamless installation on your iPhone/Android at the gym and across your local LAN:

### Option A: Reverse Proxy via Nginx Proxy Manager / Traefik / Caddy (Recommended)
Place a reverse proxy in front of the container port `8085`:

#### Caddy Example (Automatic DuckDNS or Let's Encrypt SSL):
```caddy
workout.your-domain.com {
    reverse_proxy 192.168.1.X:8085
}
```

#### Nginx Configuration Example:
```nginx
server {
    listen 443 ssl http2;
    server_name workout.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/workout.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/workout.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8085;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for Watch sync
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 4. Mobile Installation Instructions

1. Open `https://workout.your-domain.com` on your mobile device.
2. **iOS (Safari)**:
   - Tap the **Share** button at the bottom of the screen.
   - Select **Add to Home Screen**.
   - The app launches in full standalone mode with no browser URL bar.
3. **Android (Chrome)**:
   - Tap the three dots menu or the **"Install Overload App"** banner at the bottom.
   - Tap **Install**.

---

## 5. Maintenance & Data Backup

- **Backup Database**:
  ```bash
  docker cp workout_app:/app/data/workout_app.db /opt/backups/workout_app_$(date +%F).db
  ```
- **Update Application**:
  ```bash
  git pull
  docker compose up -d --build
  ```
- **Check Health Endpoint**:
  ```bash
  curl http://127.0.0.1:8085/health
  # Returns {"status": "ok", "service": "workout-api"}
  ```
