import os
import json
from google import genai

MODEL = "gemini-1.5-flash"
TEXT_MODEL = "gemini-1.5-pro" 

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

MODEL = "gemini-2.0-flash"

PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# ---- SINGLETON CLIENT (no name collisions) ----
_client_instance = None
def genai_client():
    global _client_instance
    if _client_instance is None:
        _client_instance = genai.Client(
            vertexai=True,
            project=PROJECT,
            location=LOCATION,
        )
    return _client_instance

# ---- Parsers ----
def parse_receipt_gcs(gcs_uri: str) -> dict:
    prompt = (
        "Extract normalized expense fields from this receipt image. "
        "Return strictly valid JSON per the schema. Omit unknowns."
    )
    client = genai_client()
    resp = client.models.generate_content(
        model=MODEL,  # <-- was "gemini-2.0-flash"
        contents=[{"role": "user", "parts": [
            {"text": prompt},
            {"file_data": {"file_uri": gcs_uri}}
        ]}],
        config={
            "response_mime_type": "application/json",
            "response_schema": SCHEMA
        },
    )
    return getattr(resp, "parsed", {})

def parse_free_text(text: str) -> dict:
    client = genai_client()
    prompt = (
        "Extract merchant, subtotal, tax, tip, total, currency, datetime, category "
        f"from: {text}. Return JSON with those keys."
    )
    resp = client.models.generate_content(
        model=TEXT_MODEL,  # <-- was "gemini-1.5-pro-002"
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json"},
    )
    if hasattr(resp, "parsed") and isinstance(resp.parsed, dict):
        return resp.parsed
    try:
        import json
        return json.loads(getattr(resp, "text", "{}") or "{}")
    except Exception:
        return {"raw": getattr(resp, "text", "")}
