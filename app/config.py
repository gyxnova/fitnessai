import os 
from pathlib import Path 

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")
SQL_DIR = REPO_ROOT / "sql"


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")  
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET")


required = ["DB_HOST", "DB_PORT","DB_NAME","DB_USER","DB_PASSWORD", "JWT_SECRET"]

for name in required:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")

if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters")