import os 
from pathlib import Path 

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")
SCHEMA_PATH = REPO_ROOT / "schema.sql"


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")  
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


required = ["DB_HOST", "DB_PORT","DB_NAME","DB_USER","DB_PASSWORD"]

for name in required:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")