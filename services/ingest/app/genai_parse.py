import os
import json
from google import genai

MODEL = "gemini-2.0-flash-001"
TEXT_MODEL = "gemini-2.0-flash-001"

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

MODEL = "gemini-1.5-flash-002"
TEXT_MODEL = "gemini-1.5-flash-002" 

PROJECT  = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-east5")

_client = None
def genai_client():
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    return _client

def list_models():
    # Returns simple list of model short names
    names = []
    for m in genai_client().models.list():
        # m.name is the full path; keep only the tail (model id)
        names.append(m.name.split("/models/")[-1])
    return names

def _choose_model(preferred: list[str]) -> str:
    available = set(list_models())
    for m in preferred:
        if m in available:
            return m
    # last resort: try any gemini-* in region
    any_gemini = [m for m in available if m.startswith("gemini-")]
    if not any_gemini:
        raise RuntimeError(f"No Gemini models available in {LOCATION}. Available: {sorted(available)}")
    return sorted(any_gemini)[0]

# keep one place to resolve models
def _text_model():
    return _choose_model([
        "gemini-2.0-flash-001",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
    ])

def _image_model():
    # same fallbacks for the receipt+JSON call
    return _text_model()

def parse_receipt_gcs(gcs_uri: str) -> dict:
    client = genai_client()
    resp = client.models.generate_content(
        model=_image_model(),
        contents=[{"role":"user","parts":[
            {"text": "Extract normalized expense fields as JSON per schema. Omit unknowns."},
            {"file_data": {"file_uri": gcs_uri}}
        ]}],
        config={"response_mime_type":"application/json","response_schema": SCHEMA},
    )
    return getattr(resp, "parsed", {}) or {}

def parse_free_text(text: str) -> dict:
    client = genai_client()
    prompt = (
        "Extract merchant, subtotal, tax, tip, total, currency, datetime, category from: "
        f"{text}\nReturn strictly valid JSON with only those keys."
    )
    resp = client.models.generate_content(
        model=_text_model(),
        contents=[{"role":"user","parts":[{"text": prompt}]}],
        config={"response_mime_type":"application/json"},
    )
    if hasattr(resp, "parsed") and isinstance(resp.parsed, dict):
        return resp.parsed
    try:
        return json.loads(getattr(resp, "text", "{}") or "{}")
    except Exception:
        return {"raw": getattr(resp, "text", "")}
