# Esaku API – Staging Deployment Documentation

This document describes the **complete, production-grade deployment** of the **Esaku FastAPI (staging)** application on a VPS using:

- FastAPI
- `uv` (Astral)
- Uvicorn workers
- MySQL
- Nginx
- systemd
- No domain, no SSL (port-based access)

It also includes **all post-deployment operational commands** (restart, logs, migrations, troubleshooting).

---

## 1. Architecture Overview

```
Client Browser
   ↓
http://SERVER_IP:9090
   ↓
Nginx (reverse proxy)
   ↓
FastAPI (uv + uvicorn, systemd)
   ↓
MySQL (localhost)
```

---

## 2. Server Requirements

- Ubuntu 20.04 / 22.04
- Python 3.10+
- Nginx
- MySQL Server
- Git
- Internet access

---

## 3. Global Installation of uv (MANDATORY)

`uv` **must be globally executable** for systemd and `www-data`.

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Copy uv binaries globally

```bash
sudo cp /root/.local/bin/uv /usr/local/bin/uv
sudo cp /root/.local/bin/uvx /usr/local/bin/uvx
sudo chown root:root /usr/local/bin/uv /usr/local/bin/uvx
sudo chmod 755 /usr/local/bin/uv /usr/local/bin/uvx
```

### Verify

```bash
sudo -u www-data uv --version
```

---

## 4. Project Location & Permissions

### Create project directory

```bash
sudo mkdir -p /var/www/esaku-api-staging
sudo chown -R www-data:www-data /var/www/esaku-api-staging
```

### Clone repository

```bash
sudo -u www-data git clone <REPO_URL> /var/www/esaku-api-staging
```

Expected structure:

```
/var/www/esaku-api-staging
├── pyproject.toml
├── uv.lock
├── alembic/
├── src/
│   └── main.py
└── .env
```

---

## 5. Environment Variables (.env)

```bash
sudo nano /var/www/esaku-api-staging/.env
```

```env
APP_ENV=staging

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=esaku_user
MYSQL_PASSWORD=strong_password
MYSQL_DATABASE=esaku_staging

DATABASE_URL=mysql+aiomysql://esaku_user:strong_password@127.0.0.1:3306/esaku_staging
```

```bash
sudo chown www-data:www-data /var/www/esaku-api-staging/.env
sudo chmod 600 /var/www/esaku-api-staging/.env
```

---

## 6. uv Cache Directory (IMPORTANT)

```bash
sudo mkdir -p /var/www/.cache/uv
sudo chown -R www-data:www-data /var/www/.cache
sudo chmod -R 755 /var/www/.cache
```

---

## 7. MySQL Setup

```bash
sudo mysql
```

```sql
CREATE DATABASE esaku_staging CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'esaku_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON esaku_staging.* TO 'esaku_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 8. Manual App Test (Pre-systemd)

```bash
cd /var/www/esaku-api-staging
sudo -u www-data uv run uvicorn main:app \
  --app-dir src \
  --host 127.0.0.1 \
  --port 9091
```

Test:
```bash
curl http://127.0.0.1:9091/docs
```

---

## 9. systemd Service Configuration

```bash
sudo nano /etc/systemd/system/esaku-api-staging.service
```

```ini
[Unit]
Description=Esaku API Staging (FastAPI via uv)
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/esaku-api-staging

EnvironmentFile=/var/www/esaku-api-staging/.env
Environment="UV_CACHE_DIR=/var/www/.cache/uv"

ExecStart=/usr/local/bin/uv run uvicorn main:app \
  --app-dir src \
  --host 127.0.0.1 \
  --port 9091 \
  --workers 2

Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

### Enable service

```bash
sudo systemctl daemon-reload
sudo systemctl start esaku-api-staging
sudo systemctl enable esaku-api-staging
```

---

## 10. Nginx Configuration (Port 9090)

```bash
sudo nano /etc/nginx/sites-available/esaku-api-staging
```

```nginx
server {
    listen 9090;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:9091;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60;
        proxy_read_timeout 300;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/esaku-api-staging /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 11. Firewall

```bash
sudo ufw allow 9090
sudo ufw reload
```

---

## 12. Database Migrations & Seeding (Post Deployment)

### Apply migrations

```bash
cd /var/www/esaku-api-staging
sudo -u www-data uv run alembic upgrade head
```

### Generate migration (staging only)

```bash
sudo -u www-data uv run alembic revision --autogenerate -m "message"
```

### Seed data

```bash
sudo -u www-data uv run python src/db/seed.py
sudo -u www-data uv run python src/db/apply_pod_penalties.py
sudo -u www-data uv run python src/management/apply_pod_penalties.py
```

---

## 13. Post-Deployment Operations (VERY IMPORTANT)

### Restart application

```bash
sudo systemctl restart esaku-api-staging
```

### Stop application

```bash
sudo systemctl stop esaku-api-staging
```

### Start application

```bash
sudo systemctl start esaku-api-staging
```

### View application logs (live)

```bash
journalctl -u esaku-api-staging -f
```

### View last 100 log lines

```bash
journalctl -u esaku-api-staging -n 100 --no-pager
```

### Nginx error logs

```bash
sudo tail -f /var/log/nginx/error.log
```

### Nginx access logs

```bash
sudo tail -f /var/log/nginx/access.log
```

### Check listening ports

```bash
ss -tulnp | grep 9090
ss -tulnp | grep 9091
```

---

## 14. Application Access

- API Root:
  ```
  http://SERVER_IP:9090
  ```

- Swagger Docs:
  ```
  http://SERVER_IP:9090/docs
  ```

---

## 15. Best Practices & Notes

- ❌ Never use `--reload` on server
- ❌ Do not expose uvicorn directly
- ✅ Always run migrations as `www-data`
- ✅ Keep `uv.lock` committed
- ✅ Use separate DB users per environment
- ✅ systemd handles restarts & crashes

---

## 16. Troubleshooting Quick Guide

| Issue | Command |
|-----|--------|
| App not starting | `journalctl -u esaku-api-staging -f` |
| 502 Bad Gateway | `ss -tulnp | grep 9091` |
| Nginx issue | `nginx -t` |
| DB issue | `mysql -u esaku_user -p esaku_staging` |

---

## ✅ Deployment Status

✔ Production-grade staging deployment
✔ Safe permissions
✔ uv correctly installed
✔ Nginx reverse proxy working
✔ MySQL connected

---

**End of Documentation**

