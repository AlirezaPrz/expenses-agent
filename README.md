# Expenses Agent – Ingest Service

Endpoints:
- `GET /health` – sanity check
- `POST /text` – form-encoded { text } -> parses with Gemini -> stores in Firestore
- `POST /upload-receipt` – file upload -> stores to GCS -> Gemini parses -> Firestore
- `GET /report?days=30` – sums totals by category (simple Firestore aggregation)

Env (Cloud Run):
- `BUCKET` (required) – your GCS bucket name
- Optional: `DEFAULT_USER`, `DEFAULT_CURRENCY`

This service uses Google GenAI SDK with Vertex AI (ADC) – no API key required on Cloud Run.
