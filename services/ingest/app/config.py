import os

# Required at deploy time (set in Cloud Run UI)
BUCKET = os.environ["BUCKET"]

# Project/region come from Cloud Run env automatically, but we set sane defaults
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

# Make Google GenAI SDK use Vertex AI with ADC (no API key needed on Cloud Run)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
os.environ.setdefault("GOOGLE_CLOUD_REGION", REGION)

DEFAULT_USER = os.environ.get("DEFAULT_USER", "demo")
DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "CAD")
