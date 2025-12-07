import os

# DEBUG – read from environment (Render)
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".onrender.com",
]

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# SECRET_KEY – don't hardcode in production
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key-change-this"  # fallback for local only
)
