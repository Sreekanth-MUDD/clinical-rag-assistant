#   RCG Scientific Assistant

*A Retrieval-Augmented Generation (RAG) System for Clinical Documents*

---

## 🌍 Why This Project Matters

Clinical research produces **vast volumes of complex documentation** — endpoint models, prognostic models, and natural history of disease studies. These documents are often locked inside lengthy PDFs, making it difficult for researchers to quickly extract insights, compare trials, or validate endpoints.

The ** RCG Scientific Assistant** transforms static documents into **interactive, queryable knowledge**. By combining document ingestion, vector search, reranking, and LLM synthesis, researchers can:

- Rapidly ingest experiment results  
- Ask natural language questions  
- Compare multiple trials side by side  
- Receive **precise, citation-backed answers** in real time  

This accelerates scientific workflows, reduces manual effort, and ensures that critical insights are never lost.

---

## 🏗️ High-Level Design (HLD)

### **System Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Frontend   │  │  Auth Module │  │  Chat UI (SSE)       │  │
│  │  (HTML/CSS/  │  │              │  │  Real-time Streaming │  │
│  │   JS)        │  │  JWT/OAuth2  │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            ↓ HTTPS/SSE
┌─────────────────────────────────────────────────────────────────┐
│                      API GATEWAY LAYER                          │
│  FastAPI Server (Uvicorn)                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Routes:                                                  │   │
│  │  • /api/auth/register, /login                          │   │
│  │  • /api/experiments (CRUD)                             │   │
│  │  • /api/experiments/{id}/documents (CRUD + upload)    │   │
│  │  • /api/chat/query (SSE streaming)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                         │
│  ┌─────────────────────┐  ┌────────────────────────────┐        │
│  │  Auth Service       │  │  Document Ingestion        │        │
│  │  • Password hash    │  │  • PDF parsing (PyPDF)     │        │
│  │  • JWT generation   │  │  • Table extraction        │        │
│  │  • Token validation │  │  • Text chunking           │        │
│  └─────────────────────┘  └────────────────────────────┘        │
│                                                                  │
│  ┌─────────────────────┐  ┌────────────────────────────┐        │
│  │  Retrieval Engine   │  │  LLM Integration           │        │
│  │  • Vector search    │  │  • OpenAI GPT-4o           │        │
│  │  • Re-ranking       │  │  • Ollama (local)          │        │
│  │  • Experiment scope │  │  • Streaming response      │        │
│  └─────────────────────┘  └────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATA & STORAGE LAYER                         │
│  ┌────────────────────┐  ┌──────────────────────────┐           │
│  │  PostgreSQL DB     │  │  Vector Store (pgvector) │           │
│  │  (Primary)         │  │  (HNSW index)            │           │
│  │  • Users table     │  │  • Embeddings            │           │
│  │  • Experiments     │  │  • Document chunks       │           │
│  │  • Documents       │  │  • Metadata filtering    │           │
│  │  • Sessions        │  │                          │           │
│  └────────────────────┘  └──────────────────────────┘           │
│                                                                  │
│  ┌────────────────────┐  ┌──────────────────────────┐           │
│  │  SQLite (Fallback) │  │  Local Vector Store      │           │
│  │  (if PG down)      │  │  (in-memory JSON)        │           │
│  └────────────────────┘  └──────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### **Data Flow Diagram**

```
Document Upload
     ↓
1. File received → async ingestion task
     ↓
2. PDF Parsing (PyPDF + pdfplumber)
     ├─ Extract text
     ├─ Extract tables → markdown
     └─ Combine into pages
     ↓
3. Chunking (LangChain RecursiveCharacterTextSplitter)
     ├─ chunk_size: 1000 chars
     ├─ overlap: 200 chars
     └─ Metadata: experiment_id, document_id, page_number
     ↓
4. Embedding Generation (OpenAI / Ollama)
     └─ Store vectors + metadata in pgvector
     ↓
5. Status updates: pending → processing → ready

User Query
     ↓
1. User selects experiments → scopes vector search
     ↓
2. Query embedding + metadata filter (experiment_id in [...])
     ↓
3. pgvector similarity search (top-15, HNSW index)
     ↓
4. Re-ranking (SentenceTransformers CrossEncoder) → top-5
     ↓
5. LLM synthesis (GPT-4o or Ollama llama3)
     ├─ System prompt: cite sources
     ├─ Context: [Source 1], [Source 2], ...
     └─ Stream tokens via SSE
     ↓
6. Frontend renders real-time streaming + sources carousel
```

### **Authentication Flow**

```
Registration / Login
     ↓
1. Client sends username + password (HTTPS)
     ↓
2. Backend validates:
   ├─ Username: 3-50 chars, alphanumeric + [_-]
   ├─ Password: 8+ chars, uppercase, digit
   └─ Username uniqueness
     ↓
3. Hash password (bcrypt, 12 rounds)
     ↓
4. Store in DB or return error
     ↓
5. Generate JWT token (HS256, exp: 24hrs)
     ↓
6. Client stores token in localStorage
     ↓
7. All subsequent requests: Authorization: Bearer {token}
```

---

## 🚀 Key Features

- **Fast Ingestion Pipeline**: PDF parsing with `pypdf` and table extraction via `pdfplumber`. Structured tabular markdown ensures readability for both humans and LLMs.  
- **pgvector Vector Store**: PostgreSQL with `pgvector` extension, optimized using **HNSW index** (`m=16`, `ef_construction=128`) for ultra-fast queries.  
- **Reranker Stage**: Lightweight `sentence-transformers` cross-encoder re-scores retrieved documents before LLM synthesis.  
- **Scoped Retrieval**: Queries limited strictly to selected experiment IDs for accuracy.  
- **Dual LLM Providers**: Configurable switch between **OpenAI GPT-4o** and local **Ollama** models (`llama3`).  
- **Real-Time Streaming**: SSE token-by-token streaming for conversational exploration.  
- **Secure Access**: JWT-based authentication with password strength validation.  
- **Premium UI**: branded galactic-dark theme with glassmorphism panels, blur orbs, and micro-animations.  

---

## ⚙️ Tech Stack

- **Backend**: FastAPI, Uvicorn, SQLAlchemy (Async), PostgreSQL + pgvector  
- **LangChain**: Embedding models, chat wrappers, vector store integration  
- **PDF Extraction**: `pypdf`, `pdfplumber`  
- **Reranking**: `sentence-transformers`  
- **Frontend**: HTML5, CSS3, JavaScript (SSE streaming)  
- **Deployment**: Docker Compose (PostgreSQL containerized)  

---

## 🔐 Security Features

### Authentication & Authorization
- **Password Hashing**: bcrypt with 12 salt rounds
- **JWT Tokens**: HS256 algorithm, 24-hour expiration
- **Input Validation**: All schemas validated with Pydantic validators
- **CORS**: Configurable for production deployment

### Data Protection
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy ORM
- **File Upload Validation**: PDF-only, 10MB size limit
- **Experiment Scoping**: Users can only query selected experiment IDs
- **Local Deployment**: Ollama support for on-premise data security

---

## 🔧 Setup & Running

### 1. Prerequisites
- [Docker & Docker Compose](https://www.docker.com/products/docker-desktop/)  
- Python 3.10+  

### 2. Run Database
```bash
docker-compose up -d
```

### 3. Setup Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Configure environment variables:
```bash
cp .env.example .env
```

**IMPORTANT**: Update `.env` with strong, unique values:
```env
# Required - Use a strong random SECRET_KEY (32+ chars)
SECRET_KEY=your_strong_random_key_here

# API Keys
OPENAI_API_KEY=sk-...  # or leave empty for Ollama

# Database (change default credentials for production)
DATABASE_URL=postgresql+asyncpg://sanofi_admin:strong_password@localhost:5432/rag_clinical_db
DATABASE_SYNC_URL=postgresql+psycopg://sanofi_admin:strong_password@localhost:5432/rag_clinical_db

# LLM Provider
LLM_PROVIDER=openai  # or 'ollama'
```

Run server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Run Frontend
```bash
cd ../frontend
python -m http.server 3000
```
Open browser → `http://localhost:3000`

---

## 🧪 Walkthrough

1. **Sign Up / Sign In** → Access RCG dashboard.  
   - Username: 3-50 characters, alphanumeric + hyphens/underscores
   - Password: 8+ characters, includes uppercase letter and digit

2. **Create Experiment Run** → Define trial metadata.  
   - Select model type: Prognostic, Endpoint Analysis, Natural History, or Comparator

3. **Ingest Documentation** → Upload PDFs → parsed, chunked, embedded.  
   - Monitor ingestion status: pending → processing → ready
   - Supports multiple documents per experiment

4. **Ask Queries** → Natural language questions with citation-backed answers.  
   - Results cite sources: [Source 1], [Source 2], etc.
   - See page numbers and content snippets

5. **Cross-Experiment Comparison** → Select multiple trials → side-by-side synthesis.  
   - Compare demographics, endpoints, outcomes across experiments

---

## 🔒 Local Deployment with Ollama

For full data privacy and on-premise deployment:

```bash
ollama pull nomic-embed-text
ollama pull llama3
```

Update `.env`:
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_LLM_MODEL=llama3
```

Restart backend → all processing remains **on-premise**, no API calls to external services.

---

## 🌟 Impact for Researchers

- **Accelerates discovery**: No manual searching through hundreds of pages.  
- **Improves accuracy**: Scoped retrieval tied to experiment IDs.  
- **Supports compliance**: Local deployment keeps sensitive data secure.  
- **Enhances collaboration**: Share queries and source-backed answers across teams.  

---

## ⚠️ Known Limitations & Future Enhancements

### Current Limitations
- **Single-user (local)**: No multi-tenant isolation yet
- **No audit logging**: Consider adding compliance logging for clinical data
- **Basic re-ranking**: Uses cross-encoder; consider learning-to-rank for production

### Roadmap
- [ ] Multi-tenant support with org-level experiment grouping
- [ ] Audit logging & compliance tracking
- [ ] Advanced re-ranking with learned-to-rank models
- [ ] Integration with trial management platforms (Medidata, Veeva)
- [ ] Mobile app for field researchers
- [ ] Real-time collaboration features

---

## 📌 Conclusion

The ** RCG Scientific Assistant** is a **new paradigm for clinical research knowledge management**. By combining structured ingestion, vector search, reranking, and LLM synthesis, it empowers researchers to move faster, compare smarter, and trust their insights.

---

## 📄 License

MIT License. See `LICENSE` file for details.
