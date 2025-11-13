# Expenses Agent – Ingest Service

A small FastAPI service that powers an AI expense-tracking agent on Google Cloud.

The service exposes a couple of HTTP endpoints that:
- Use **Gemini 2.0 Flash** (via the `google-genai` SDK on **Vertex AI**) to parse
  natural-language descriptions of expenses into structured JSON.
- Store those parsed expenses in **Cloud Firestore**.
- Aggregate expenses by category over the last _N_ days for reporting.
- Are consumed as **tools** by a Vertex AI *Conversational Agent* (Agent Builder).

---

## Architecture

- **Runtime**: FastAPI app running on **Cloud Run** (Python 3.11).
- **AI model**: `gemini-2.0-flash-001` on Vertex AI, via the `google-genai` SDK.
- **Storage**: Firestore in Native Mode (database ID `(default)`), collection:
  `users/{DEFAULT_USER}/transactions`.
- **Agent integration**: Vertex AI Agent Builder uses two tools:
  - `log_expense` → calls `POST /text-json`
  - `get_report` → calls `GET /report?days=…`

---

## Endpoints

### `GET /`

Simple liveness check.

```bash
curl https://<CLOUD_RUN_URL>/
# -> "expenses-ingest alive"
````

---

### `GET /healthz`

Basic health + configuration check.

Response:

```json
{
  "ok": true,
  "project": "your-gcp-project-id"
}
```

---

### `POST /text-json`

**Purpose:** Parse a natural-language description of an expense, store it in Firestore, and return both the parsed fields and the saved document.

**Request body (JSON):**

```json
{
  "text": "I bought a coffee at Starbucks for 4.75 CAD today, tip 0.50."
}
```

**What happens:**

1. The text is sent to Gemini 2.0 Flash with a structured JSON schema:

   * `merchant`, `datetime`, `currency`, `subtotal`, `tax`, `tip`, `total`,
     `category`, and optional `line_items`.
2. The service normalizes the data and writes a document under:

   * `users/{DEFAULT_USER}/transactions/{uuid}` in Firestore.
3. The inserted document ID is returned.

**Response (example):**

```json
{
  "saved": true,
  "parsed": {
    "merchant": "Starbucks",
    "total": 4.75,
    "category": "coffee",
    "currency": "CAD",
    "tip": 0.5,
    "datetime": "2025-11-12T08:30:00Z"
  },
  "doc": {
    "user_id": "demo",
    "ts": "2025-11-12T08:30:00+00:00",
    "merchant": "Starbucks",
    "currency": "CAD",
    "subtotal": 0.0,
    "tax": 0.0,
    "tip": 0.5,
    "total": 4.75,
    "category": "coffee",
    "source": "text",
    "raw_uri": "",
    "id": "5a6f2be1-1239e-4542141d6-ba23-44ag2323-213s168cdf"
  }
}
```

This endpoint is used by the Vertex AI tool:

* **Tool name:** `log_expense`
* **Method:** `POST /text-json`

---

### `GET /report?days=30`

**Purpose:** Aggregate expenses by category over the last *N* days.

* `days` (query, integer, default `30`): number of days to look back.

**Example:**

```bash
curl "https://<CLOUD_RUN_URL>/report?days=30"
```

**Response (example):**

```json
{
  "days": 30,
  "by_category": [
    { "category": "rent",          "total": 1200.0 },
    { "category": "grocery",       "total": 456.7 },
    { "category": "utilities",     "total": 198.49 },
    { "category": "health",        "total": 187.29 },
    { "category": "shopping",      "total": 179.89 },
    { "category": "entertainment", "total": 87.74 },
    { "category": "coffee",        "total": 51.0 },
    { "category": "transport",     "total": 47.75 },
    { "category": "other",         "total": 8.5 }
  ]
}
```

Under the hood, this endpoint:

* Reads all documents from `users/{DEFAULT_USER}/transactions`.
* Filters to those with `ts` within the last `days` days.
* Sums `total` per category, rounded to 2 decimals and sorted.

This endpoint is used by the Vertex AI tool:

* **Tool name:** `get_report`
* **Method:** `GET /report?days={days}`

---

## Environment variables

The service is configured via environment variables (especially in Cloud Run):

* `GOOGLE_CLOUD_PROJECT` (set automatically on Cloud Run)
* `DEFAULT_USER` (optional, default: `"demo"`)
* `DEFAULT_CURRENCY` (optional, default: `"CAD"`)

Additionally, `config.py` sets:

* `GOOGLE_GENAI_USE_VERTEXAI=True`
* `GOOGLE_CLOUD_REGION` (default `us-central1`)

These help the `google-genai` client talk to Vertex AI with Application Default Credentials.

---

## Running locally (for testing)

1. **Create and activate a virtualenv** (optional but recommended):

   ```bash
   cd services/ingest
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set env vars (at minimum):**

   ```bash
   export GOOGLE_CLOUD_PROJECT=<your-project-id>
   export DEFAULT_USER=demo
   export DEFAULT_CURRENCY=CAD
   ```

   Make sure you’ve authenticated with:

   ```bash
   gcloud auth application-default login
   ```

   and that your project has:

   * A Firestore database (`(default)`, Native mode)
   * Vertex AI API enabled.

4. **Run the app:**

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8080 --reload
   ```

5. Open:

   * Swagger docs: `http://localhost:8080/docs`
   * Root check: `http://localhost:8080/`
   * Health: `http://localhost:8080/healthz`

---

## Deploying to Cloud Run

From the `services/ingest` directory:

```bash
gcloud builds submit --tag gcr.io/$GOOGLE_CLOUD_PROJECT/expenses-ingest

gcloud run deploy expenses-ingest \
  --image gcr.io/$GOOGLE_CLOUD_PROJECT/expenses-ingest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

Make sure Firestore is initialized:

* Go to **Firestore** in the Cloud Console.
* Create database `(default)` in Native mode.

After deployment, note your service URL and plug it into your Vertex AI tools:

* `log_expense` → `POST {CLOUD_RUN_URL}/text-json`
* `get_report` → `GET {CLOUD_RUN_URL}/report?days={days}`

---

## Receipt parsing

The service can optionally:

* Accept a receipt image via `POST /upload-receipt`.
* Store it in a GCS bucket (`BUCKET` env variable).
* Call Gemini 2.0 Flash with `file_data` + JSON schema.
* Store the parsed expense in Firestore.

This is currently not wired into the Vertex AI agent tools.