# Clinical RAG Assistant

A Retrieval-Augmented Generation (RAG) system designed to index and query clinical trial documents and biostatistics data. It runs locally using **Ollama** and supports **PGVector** for vector storage.

---

## ✨ Features
- 📄 **Document Ingestion**: Extract text and table data (converted to Markdown) from clinical PDFs.
- 💬 **Document-centric Chat**: Each document has its own dedicated RAG assistant chat interface with persistent chat history.
- � **SSE Streaming Chat**: Real-time response streaming from Ollama with inline source citations.
- 🗄️ **Robust Database**: Uses PostgreSQL & PGVector, falling back to SQLite + In-Memory vector store if PostgreSQL is unavailable.
- 🔒 **Secure Auth**: JWT-based user registration and login.
- 🐳 **Dockerized Stack**: Run the entire system with a single Docker Compose command.

---

## 🛠️ Tech Stack
- **Frontend**: HTML5, Vanilla JS, CSS (Modern dark glassmorphism theme)
- **Backend**: FastAPI (Python 3.11), SQLAlchemy, Uvicorn, PyPDF, pdfplumber
- **AI/RAG**: LangChain, Ollama (`llama3` and `nomic-embed-text` embeddings)
- **Database**: PostgreSQL with `pgvector` extension

---

## 🚀 Quick Start (Docker Compose)

### 1. Prerequisites
Ensure Ollama is running on your host machine with the required models pulled:
```bash
ollama pull llama3
ollama pull nomic-embed-text
```

### 2. Start the Stack
From the project root directory, run:
```bash
docker-compose up --build
```
This starts:
- **Database**: PostgreSQL + pgvector at `localhost:5432`
- **Backend API**: FastAPI server at `localhost:8000`
- **Frontend UI**: Nginx server at `localhost:3000`

Access the application at **[http://localhost:3000](http://localhost:3000)**.

---

## 🔧 Local Development (Without Docker)

### Backend setup:
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment, then install dependencies:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and adjust settings.
4. Run the API server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

### Frontend setup:
1. Navigate to the frontend folder:
   ```bash
   cd ../frontend
   ```
2. Run a simple local server:
   ```bash
   python -m http.server 3000
   ```
3. Open **[http://localhost:3000](http://localhost:3000)** in your browser.
