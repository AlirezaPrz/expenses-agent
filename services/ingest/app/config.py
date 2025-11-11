import os
BUCKET = os.environ.get("BUCKET")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault("GOOGLE_CLOUD_REGION", REGION)
DEFAULT_USER = os.environ.get("DEFAULT_USER", "demo")
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "CAD")
