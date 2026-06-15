
```markdown
# Sanofi RCG Scientific Assistant  
*A Retrieval-Augmented Generation (RAG) System for Clinical Documents*

---

## 🌍 Why This Project Matters

Clinical research produces **vast volumes of complex documentation** — endpoint models, prognostic models, and natural history of disease studies. These documents are often locked inside lengthy PDFs, making it difficult for researchers to quickly extract insights, compare trials, or validate endpoints.

The **Sanofi RCG Scientific Assistant** transforms static documents into **interactive, queryable knowledge**. By combining document ingestion, vector search, reranking, and LLM synthesis, researchers can:

- Rapidly ingest experiment results  
- Ask natural language questions  
- Compare multiple trials side by side  
- Receive **precise, citation-backed answers** in real time  

This accelerates scientific workflows, reduces manual effort, and ensures that critical insights are never lost.

---

## 🚀 Key Features

- **Fast Ingestion Pipeline**: PDF parsing with `pypdf` and table extraction via `pdfplumber`. Structured tabular markdown ensures readability for both humans and LLMs.  
- **pgvector Vector Store**: PostgreSQL with `pgvector` extension, optimized using **HNSW index** (`m=16`, `ef_construction=128`) for ultra-fast queries.  
- **Reranker Stage**: Lightweight `sentence-transformers` cross-encoder re-scores retrieved documents before LLM synthesis.  
- **Scoped Retrieval**: Queries limited strictly to selected experiment IDs for accuracy.  
- **Dual LLM Providers**: Configurable switch between **OpenAI GPT-4o** and local **Ollama** models (`llama3`).  
- **Real-Time Streaming**: SSE token-by-token streaming for conversational exploration.  
- **Secure Access**: JWT-based authentication for clinical data protection.  
- **Premium UI**: Sanofi-branded galactic-dark theme with glassmorphism panels, blur orbs, and micro-animations.  

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    A[Experiment Completed] --> B[Raw Docs -> S3]
    A --> C[Metadata -> PostgreSQL]
    B --> D[Async Trigger / Event]
    D --> E[Fetch Doc from S3]
    E --> F[Parse & Chunk (LangChain + PyMuPDF)]
    F --> G[Generate Embeddings]
    G --> H[Store in PostgreSQL (pgvector + Experiment ID)]
    I[User Query] --> J[Query Embedding]
    J --> K[Vector Search (Scoped by Experiment ID)]
    K --> L[LLM Generates Answer]
```

---

## ⚙️ Tech Stack

- **Backend**: FastAPI, Uvicorn, SQLAlchemy (Async), PostgreSQL + pgvector  
- **LangChain**: Embedding models, chat wrappers, vector store integration  
- **PDF Extraction**: `pypdf`, `pdfplumber`  
- **Reranking**: `sentence-transformers`  
- **Frontend**: HTML5, CSS3, JavaScript (SSE streaming)  
- **Deployment**: Docker Compose (PostgreSQL containerized)  

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
Fill in `OPENAI_API_KEY` or set `LLM_PROVIDER=ollama`.

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
2. **Create Experiment Run** → Define trial metadata.  
3. **Ingest Documentation** → Upload PDFs → parsed, chunked, embedded.  
4. **Ask Queries** → Natural language questions with citation-backed answers.  
5. **Cross-Experiment Comparison** → Select multiple trials → side-by-side synthesis.  

---

## 🔒 Local Deployment with Ollama

For full data privacy:

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

Restart backend → all processing remains **on-premise**.

---

## 🌟 Impact for Researchers

- **Accelerates discovery**: No manual searching through hundreds of pages.  
- **Improves accuracy**: Scoped retrieval tied to experiment IDs.  
- **Supports compliance**: Local deployment keeps sensitive data secure.  
- **Enhances collaboration**: Share queries and source-backed answers across teams.  

---

## 📌 Conclusion

The **Sanofi RCG Scientific Assistant** is a **new paradigm for clinical research knowledge management**. By combining structured ingestion, vector search, reranking, and LLM synthesis, it empowers researchers to move faster, compare smarter, and trust their insights.

---

## 📷 Screenshots

*(Add architecture diagrams, dashboard screenshots, and ingestion flow images here)*

---

## 🤝 Contributing

Contributions are welcome! Please fork the repo, create a feature branch, and submit a pull request.

---

## 📜 License

MIT License. See `LICENSE` file for details.
```


