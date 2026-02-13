# Esaku API – Dev Server Deployment Documentation

# Enter the directory as root user

```bash
cd /eisaku-tms-bc
```

# pull the latest changes

```bash
sudo git pull
```

# install dependencies (if required)

```bash
sudo pip install -r requirements.txt
```

# run migrations (if required)

```bash
sudo alembic upgrade head
```

# Restart development server as root user

```bash
sudo systemctl restart eisaku-tms.service 
```
