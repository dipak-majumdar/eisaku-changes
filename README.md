# Eisaku TMS Backend

A FastAPI backend service with Alembic migrations and seeding utilities.

---

## 🚀 Quick Setup

### 1. Virtual Environment

```bash
python -m venv venv
```

#### Activate

- **Windows:**  
  ```
  .\venv\Scripts\activate
  ```
- **Linux/macOS:**  
  ```
  source venv/bin/activate
  ```

---

### 2. Install Dependencies

```bash
uv run python --version


```

---

### 3. Database

#### Merge heads
##### Get the heads first

```bash
uv run alembic heads
```

##### Merge the heads

```bash
uv run alembic merge -m "merge heads" 772392c1b3a2 86c35fa1acb3
```

#### Generate a new/latest migration

```bash
uv run alembic revision --autogenerate -m "migration message"
```

#### Apply existing migrations

```bash
uv run alembic upgrade head  
```

#### Seed initial data

```bash

uv run python src/db/seed.py
uv run src/db/apply_pod_penalties.py
uv run python src/management/apply_pod_penalties.py
```

---

### 4. Run the Server

```bash
# uv run uvicorn main:app --reload --port 8000 --app--dir=src
uv run uvicorn main:app --reload --app-dir src --port 9000
```

### 5. Package Intallation

``` bash
uv add "package name"
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation.

---

## 📂 Project Structure

```
project-root/
├── alembic/            # Alembic migrations
├── src/
│   ├── db/
│   │   └── seed.py     # Data seed script
│   └── main.py         # FastAPI entry point
├── venv/
├── README.md
├── alembic.ini
└── pyproject.toml
```

---

**Notes:**
- Always activate your venv before running project commands.
- Be sure to configure your database connection before running migrations or seed.
- Use Alembic for all schema changes, and the seed script to populate test/admin data.
