import os
import sys
import time
import socket
import subprocess
import signal
from urllib.parse import urlparse
import asyncio
import asyncpg
import glob
from pathlib import Path

# Minimal runner for local dev: ensures DATABASE_URL, checks DB/ES, starts backend then frontend.
DEFAULT_DB = "postgresql://sales_user:sales_pass@localhost:5432/sales_agent"
ES_URL = "http://localhost:9200"
BACKEND_URL = "http://localhost:8000"
BACKEND_CHECK_PATH = "/sessions"
UVICORN_CMD = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
STREAMLIT_CMD = [sys.executable, "-m", "streamlit", "run", "frontend/chat_interface.py", "--server.port", "8501", "--server.headless", "true"]

def ensure_database_env():
    if not os.getenv("DATABASE_URL"):
        print(f"DATABASE_URL not set. Setting default: {DEFAULT_DB}")
        os.environ["DATABASE_URL"] = DEFAULT_DB

def parse_db_host_port(db_url):
    p = urlparse(db_url)
    host = p.hostname or "localhost"
    port = p.port or 5432
    return host, port


def repo_root_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__)))


async def _test_db_auth_async(db_url: str) -> None:
    """Try to open and close a connection to check auth; raise on auth errors."""
    conn = None
    try:
        conn = await asyncpg.connect(dsn=db_url)
    finally:
        if conn is not None:
            await conn.close()


def test_db_auth(db_url: str):
    try:
        asyncio.run(_test_db_auth_async(db_url))
        return True
    except asyncpg.InvalidPasswordError:
        print("ERROR: Password authentication failed for the Postgres user in DATABASE_URL.")
        print("Remediation options:")
        print(" - Set a correct DATABASE_URL environment variable with valid user/password before running.")
        print("   PowerShell example:")
        print('     $Env:DATABASE_URL = "postgresql://user:password@localhost:5432/sales_agent"')
        print(" - Or update the Postgres user's password (psql as a superuser):")
        print('     psql -U postgres -c "ALTER USER <user> WITH PASSWORD \"<password>\";"')
        print(" - Or create the expected user and grant privileges for database 'sales_agent'.")
        sys.exit(1)
    except Exception as e:
        print(f"Warning: could not fully validate DB credentials: {e}")
        # allow flow to continue; the more definitive check will happen when backend starts
        return False


async def ensure_db_schema_async(db_url: str):
    """Connect to Postgres and execute `create_tables.sql` if present."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    sql_path = os.path.join(repo_root, 'backend', 'services', 'create_tables.sql')
    if not os.path.exists(sql_path):
        print("No create_tables.sql found, skipping schema creation.")
        return

    print(f"Applying DB schema from {sql_path}...")
    sql = Path(sql_path).read_text(encoding='utf-8')
    # asyncpg expects a connection string
    conn = None
    try:
        conn = await asyncpg.connect(dsn=db_url)
        # try executing the whole file in one go
        await conn.execute(sql)
        print("DB schema applied (create_tables.sql).")
    except Exception as e:
        print(f"Warning: failed to apply DB schema: {e}")
    finally:
        if conn:
            await conn.close()


def ensure_db_schema(db_url: str):
    try:
        asyncio.run(ensure_db_schema_async(db_url))
    except Exception as e:
        print(f"Error ensuring DB schema: {e}")


def index_csvs_to_es(es_url: str):
    """If Elasticsearch reachable, index CSVs under `data/csv` using local indexing helper."""
    try:
        import requests
        r = requests.get(es_url, timeout=2)
        if r.status_code != 200:
            print(f"Elasticsearch responded {r.status_code}; skipping CSV indexing.")
            return
    except Exception:
        print(f"Elasticsearch not reachable at {es_url}; skipping CSV indexing.")
        return

    # import the indexing helper from backend.services.elasticsearch_service
    try:
        from backend.services.elasticsearch_service import bulk_index_from_csv
    except Exception as e:
        print(f"Could not import Elasticsearch indexer: {e}")
        return

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    csv_dir = os.path.join(repo_root, 'data', 'csv')
    csv_paths = glob.glob(os.path.join(csv_dir, '*.csv'))
    if not csv_paths:
        print("No CSV files found to index.")
        return

    for p in csv_paths:
        print(f"Indexing {p} to Elasticsearch...")
        try:
            bulk_index_from_csv(p)
        except Exception as e:
            print(f"Failed indexing {p}: {e}")

def check_tcp(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def wait_for_http(url, timeout=30, interval=1):
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False

def main():
    ensure_database_env()
    db_url = os.environ["DATABASE_URL"]
    host, port = parse_db_host_port(db_url)
    print(f"Checking Postgres at {host}:{port} ...")
    if not check_tcp(host, port):
        print(f"Cannot reach Postgres at {host}:{port}.")
        print("Make sure Postgres is installed and the server is running on your machine.")
        print("Common ways to start Postgres:")
        print("  - Windows: start the 'PostgreSQL' service via Services app or use pgAdmin")
        print("If you don't have Postgres installed, download it from https://www.postgresql.org/download/")
        print("After starting Postgres, create a database named 'sales_agent' and user/password as configured in DATABASE_URL.")
        print("Example psql commands (adjust user/password as needed):")
        print("  createdb -U postgres sales_agent")
        print("  psql -U postgres -d sales_agent -c \"CREATE TABLE sessions (session_id UUID PRIMARY KEY, title TEXT, created_at TIMESTAMP DEFAULT now(), updated_at TIMESTAMP DEFAULT now());\"")
        print("  psql -U postgres -d sales_agent -c \"CREATE TABLE messages (id UUID DEFAULT gen_random_uuid() PRIMARY KEY, session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE, role TEXT, content TEXT, created_at TIMESTAMP DEFAULT now());\"")
        sys.exit(1)

    # optional ES check
    try:
        import requests
        r = requests.get(ES_URL, timeout=2)
        if r.status_code == 200:
            print("Elasticsearch reachable at", ES_URL)
            # index CSVs into ES (best-effort)
            index_csvs_to_es(ES_URL)
        else:
            print("Elasticsearch responded with status", r.status_code)
    except Exception:
        print("Elasticsearch not reachable at", ES_URL, "- continuing without ES (some features may be disabled).")

    # ensure DB schema is created (best-effort)
    try:
        ensure_db_schema(db_url)
    except Exception as e:
        print(f"Failed to ensure DB schema: {e}")

    # start backend and frontend and monitor them; restart when either exits
    def start_backend():
        print("Starting backend:", " ".join(UVICORN_CMD))
        return subprocess.Popen(UVICORN_CMD, stdout=None, stderr=None, env=os.environ.copy())

    def start_frontend():
        print("Starting Streamlit frontend:", " ".join(STREAMLIT_CMD))
        return subprocess.Popen(STREAMLIT_CMD, stdout=None, stderr=None, env=os.environ.copy())

    backend_proc = start_backend()

    # wait until backend serves (poll /sessions)
    backend_ok = wait_for_http(BACKEND_URL + BACKEND_CHECK_PATH, timeout=30)
    if not backend_ok:
        print("Backend did not become healthy within timeout. Check logs above.")
        backend_proc.terminate()
        backend_proc.wait(timeout=5)
        sys.exit(1)
    print("Backend is up.")

    frontend_proc = start_frontend()

    stop_requested = False

    def handle_sigint(signum, frame):
        nonlocal stop_requested
        print("Shutting down processes...")
        stop_requested = True
        for p in (frontend_proc, backend_proc):
            try:
                p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    # Monitor loop: if backend or frontend exit, restart them with backoff
    backoff = 1
    while not stop_requested:
        time.sleep(1)
        # monitor backend
        if backend_proc.poll() is not None:
            rc = backend_proc.returncode
            print(f"Backend exited with code {rc}; restarting in {backoff}s...")
            try:
                backend_proc = start_backend()
                # wait for the backend to become healthy before proceeding
                if not wait_for_http(BACKEND_URL + BACKEND_CHECK_PATH, timeout=30):
                    print("Restarted backend did not become healthy in time.")
                else:
                    print("Backend restarted and healthy.")
            except Exception as e:
                print(f"Failed to restart backend: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        # monitor frontend
        if frontend_proc.poll() is not None:
            rc = frontend_proc.returncode
            print(f"Frontend exited with code {rc}; restarting in {backoff}s...")
            try:
                frontend_proc = start_frontend()
            except Exception as e:
                print(f"Failed to restart frontend: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue

        # reset backoff when both are healthy
        backoff = 1

if __name__ == "__main__":
    main()
