import os
from google import genai
import google.auth

SCHEMA = {
    "type": "object",
    "properties": {
        "merchant": {"type": "string"},
        "datetime": {"type": "string", "format": "date-time"},
        "currency": {"type": "string"},
        "subtotal": {"type": "number"},
        "tax": {"type": "number"},
        "tip": {"type": "number"},
        "total": {"type": "number"},
        "category": {"type": "string", "enum": [
            "food","transport","grocery","rent","utilities","shopping","health",
            "entertainment","coffee","other"
        ]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"desc":{"type":"string"}, "qty":{"type":"number"}, "price":{"type":"number"}},
                "required": ["desc","price"]
            }
        }
    },
    "required": ["merchant","total","category"]
}

MODEL_FAST = "gemini-2.0-flash-001"

# Resolve region & project deterministically
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

def _resolve_project():
    # Prefer explicit env, then ADC project_id
    env_proj = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
    if env_proj:
        return env_proj
    creds, project_id = google.auth.default()
    return project_id

PROJECT = _resolve_project()

_client_singleton = None
def get_genai_client():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = genai.Client(
            vertexai=True,
            project=PROJECT,
            location=LOCATION,
        )
    return _client_singleton

def list_models():
    client = get_genai_client()
    return [m.name for m in client.models.list()]

def parse_receipt_gcs(gcs_uri: str) -> dict:
    prompt = ("Extract normalized expense fields from this receipt image. "
              "Return strictly valid JSON per the schema. Omit unknowns.")
    client = get_genai_client()
    resp = client.models.generate_content(
        model=MODEL_FAST,
        contents=[{"role":"user","parts":[{"text": prompt}, {"file_data":{"file_uri": gcs_uri}}]}],
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed

def parse_free_text(text: str) -> dict:
    client = get_genai_client()
    resp = client.models.generate_content(
        model=MODEL_FAST,
        contents=f"Extract merchant, subtotal, tax, tip, total, currency, datetime, category from: {text}. "
                 f"Return JSON with those keys and reasonable defaults if missing.",
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed
