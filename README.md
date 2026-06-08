# VendorIQ: AI-Powered Vendor Management Dashboard & RAG Chatbot

VendorIQ is a production-grade, enterprise vendor management dashboard integrated with a Retrieval-Augmented Generation (RAG) pipeline. The application combines real-time contractor tracking, interactive dashboard operations, token-optimized AI chat/report generation, and high-fidelity, styled executive exports (Excel/PDF) in a fully offline-capable configuration.

---

## 🚀 Key Features

### 1. Interactive Contractor Dashboard
- **Urgency-based Contractor Sorting**: Automatically sorts all contractors by their contract end date in ascending order. The most urgent/expiry-prone contracts are pinned to the top; TBD or invalid dates are sorted to the bottom.
- **Expiry Urgency Color Coding**: Dynamically styles the contract end date and remaining duration using a smooth HSL gradient from red (immediate expiry) to orange/yellow (medium term) to green (extended term).
- **Status & Class Badges**: Employs pastel-colored status tags matching the exact corporate brand specifications (`Active`, `Interviewing`, `Submitted`, `Pending`, `Terminated`), along with distinct custom badges differentiating `DIRECT` and `VENDOR` contracts.
- **Offline Library Integration**: Utilizes locally hosted copies of `exceljs.min.js` and `html2pdf.bundle.min.js` to ensure the platform operates smoothly in secure, internet-restricted intranets.

### 2. High-Fidelity Executive Exports
- **Excel Export (`ExcelJS`)**:
  - Preserves the exact 25-column sequence ordered in the UI layout.
  - Frozen headers, alternating white and soft gray zebra rows, and custom typography (Segoe UI).
  - Matches the dashboard's soft pastel background colors for contractor statuses.
  - Retains the contractor urgency expiry color gradient (red to green) and custom DIRECT/VENDOR labels.
- **PDF Export (`html2pdf.js`)**:
  - Automatically formats the dashboard table into an executive-ready A2 landscape layout.
  - Dynamically clones the live page table, strips away action buttons and interactive settings, maps list elements (like skills) to pill chips, and renders a clean header summary with report generation metadata.

### 3. Token-Optimized RAG Pipeline
- **Vector Database**: Employs **ChromaDB** with **sentence-transformers** (`BAAI/bge-small-en-v1.5` loaded locally, requiring no external embedding API keys).
- **Dynamic Context Reducer**: Deduplicates retrieved chunks, filters by cosine similarity threshold (`0.35`), and constrains context to a strict ceiling of `2500` characters, slicing cleanly at word boundaries to eliminate half-cut tokens.
- **Smart History Pruning**:
  - Standard Chat: Maintains only the last 2 turns (4 messages) to minimize prompt token overhead.
  - Report Mode: Completely clears chat history during report requests to focus LLM context budgets exclusively on data files and current instructions.

### 4. Robust AI Report Control Layer & Auto-Correction
- **FastAPI Backend Validation**: Checks that LLM responses in report modes (`WEEKLY_SUMMARY`, `COMPLIANCE`, `VENDOR`, `CONTRACTOR`) conform strictly to markdown table structures with exact, pre-defined column headers.
- **Self-Correction Retry**: If the initial LLM report generation fails table structure checks, the system transparently executes a single-run self-correction loop, instructing the model on the exact schema violation and prompting a corrected generation before streaming to the client.
- **SSE Token Streaming**: Streams generated content chunk-by-chunk using Server-Sent Events (SSE) for both standard chat and validated report responses.

### 5. Live Token Analytics & Billing Tracker
- **SQLite Database backend**: Automatically records usage metrics (prompt tokens, completion tokens, model name, and endpoint origin) to `data/metrics.db`.
- **Accurate Model-Specific Billing**: Computes costs in real time based on official Groq pricing tiers for supported models:
  - `llama-3.1-8b-instant`
  - `llama-3.1-70b-versatile`
  - `mixtral-8x7b-32768`
- **Frontend Cost Console**: Includes a live "AI Token Usage & Cost" visualizer under Settings that polls aggregated metrics via `/api/metrics/tokens` every 10 seconds.

---

## 📂 Project Directory Structure

```text
rag-cb-implementation/
├── api/
│   ├── routes/              # FastAPI router modules
│   │   ├── chat.py          # /api/chat endpoint (SSE stream, history pruning, report validation)
│   │   ├── documents.py     # /api/documents endpoint (indexing status, delete operations)
│   │   ├── ingest.py        # /api/ingest endpoint (PDF/TXT uploads to ChromaDB)
│   │   └── metrics.py       # /api/metrics endpoint (aggregate token tracking outputs)
│   ├── dependencies.py      # FastAPI Dependency Injectors (RAG pipeline singletons)
│   └── main.py              # Application entry point, MIME configuration, static file mount
├── data/                    # App data directory (ChromaDB persistence folder, metrics.db sqlite file)
├── frontend/                # Static files served at the root route (/)
│   ├── index.html           # Main frontend dashboard and controller scripts
│   ├── exceljs.min.js       # Local ExcelJS module for offline spreadsheets
│   └── html2pdf.bundle.min.js # Local html2pdf module for offline report printing
├── prompts/                 # Core prompting library
│   ├── report.py            # Report configurations, prompt templates, and structural schemas
│   └── system.py            # Main RAG and platform system context strings
├── rag/                     # RAG core modules
│   ├── ingestion.py         # File parser, text splitter, and collection populator
│   ├── pipeline.py          # Orchestrates retrieval -> system prompting -> LLM streaming
│   └── retriever.py         # Cosine similarity retrieval, chunk deduplication, context budgeting
├── services/                # Backend API service wraps
│   ├── embedding_service.py # Embedding generator interface (sentence-transformers)
│   ├── llm_service.py       # Groq completion and stream client integration
│   └── metrics_service.py   # SQLite database connection, table creation, and cost logger
├── vectorstore/             # Vector database integration layer
│   └── __init__.py          # Vector store manager factory (ChromaDB support)
├── .env                     # Environment settings (Groq key, limits, thresholds, models)
├── requirements.txt         # Core Python pip package dependencies
└── venv/                    # Python virtual environment directory
```

---

## 🛠️ Installation & Local Setup

### Prerequisites
- Python 3.10 or higher installed.
- A **Groq API Key** (Get one for free at the [Groq Console](https://console.groq.com)).

### 1. Clone & Navigate
```bash
git clone <repository-url>
cd rag-cb-implementation
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory (you can copy `.env.example` if available). Make sure the following keys are populated:

```env
# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here

# Vector Store Configurations
VECTOR_STORE=chroma
CHROMA_PERSIST_DIR=./data/chroma

# Embeddings Model (Runs locally, downloaded once ~130MB)
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# RAG & Context Slicing Parameters
DEFAULT_CHUNK_SIZE=750
DEFAULT_CHUNK_OVERLAP=150
DEFAULT_TOP_K=2
SIMILARITY_THRESHOLD=0.35
MAX_CONTEXT_CHARS=1200

# LLM Configurations
LLM_MODEL=llama-3.1-8b-instant
LLM_MAX_TOKENS=1024
CHAT_MAX_TOKENS=300
REPORT_MAX_TOKENS=400

# Server Configurations
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=*
```

### 3. Create a Virtual Environment and Install Dependencies
On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the Backend Server
Start the uvicorn development server:
```powershell
.\venv\Scripts\uvicorn.exe api.main:app --reload --port 8000
```
The application will start, warm up the singletons (loads the embedding model and verifies Groq connectivity), and serve:
- The dashboard frontend UI at: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Swagger API documentation at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🔌 API Documentation Reference

### 1. Chat & Report Generation
* **Endpoint**: `POST /api/chat`
* **Request Body**:
  ```json
  {
    "query": "Generate a compliance report for expiring documents.",
    "history": [],
    "mode": "COMPLIANCE"
  }
  ```
* **Description**: Returns a streaming text response (Server-Sent Events) containing token chunks, followed by a citation payload `data: [SOURCES] ...` and a termination token `data: [DONE]`.

### 2. Live Token Analytics
* **Endpoint**: `GET /api/metrics/tokens`
* **Description**: Returns aggregated metrics across all queries.
* **Response**:
  ```json
  {
    "total_requests": 42,
    "prompt_tokens": 12450,
    "completion_tokens": 8412,
    "total_tokens": 20862,
    "estimated_cost": 0.001295
  }
  ```

### 3. Document Ingestion
* **Endpoint**: `POST /api/ingest/file` (Form-data)
* **Parameters**: `file` (upload PDF or TXT files)
* **Description**: Parses the document, splits it into chunks, generates vector embeddings, and stores them in ChromaDB.

### 4. Health & Liveness
* **Endpoint**: `GET /api/health`
* **Description**: Inspects Groq connection state and counts indexed vector documents. Used by the frontend header indicators.

---

## 🎨 Export Formatting & Column Orders

For all Excel and PDF exports, the columns are preserved exactly in the following sequence:

1. **Contractor**
2. **Client**
3. **Base Location**
4. **Latest Update**
5. **Contract Type**
6. **Client Emp Code**
7. **Source Name**
8. **Contract Start Date**
9. **Contract End Date**
10. **Duration As Of Date**
11. **Skills**
12. **Laptop**
13. **Reporting Manager**
14. **Vendor Rate Card**
15. **Client Rate Card**
16. **Commission**
17. **Margin**
18. **Margin %**
19. **Last RC Received**
20. **Last RC Date**
21. **RC Duration**
22. **Office Location**
23. **Vendor**
24. **Billing Rate**
25. **Status**

### Urgency Expiry Ranges:
- **Red (Urgent)**: Expiry <= 30 days
- **Orange (Intermediate)**: Expiry between 31 and 90 days
- **Yellow (Approaching)**: Expiry between 91 and 180 days
- **Green (Extended)**: Expiry > 180 days

### Status Pastel Colors:
- **Active**: Pastel Green (Text: Dark Green)
- **Interviewing**: Pastel Blue (Text: Dark Blue)
- **Submitted**: Pastel Purple (Text: Dark Purple)
- **Pending**: Pastel Orange (Text: Dark Orange)
- **Terminated**: Pastel Gray/Red (Text: Dark Gray)
