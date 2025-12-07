import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# DEBUG – Render will control this with env var
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "alumini-connect-4xog.onrender.com",
    "localhost",
    "127.0.0.1",
    ".onrender.com",
]

# SECRET_KEY – don't hardcode in production
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-this"  # fallback for local only
)

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
