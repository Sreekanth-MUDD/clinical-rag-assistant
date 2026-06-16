import os
import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from pypdf import PdfReader
import pdfplumber
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument
from app.config import settings
from app.database import Document as DBDocument, Experiment, AsyncSessionLocal, USE_POSTGRES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing langchain-postgres, fallback to langchain-community
try:
    from langchain_postgres import PGVector
except ImportError:
    try:
        from langchain_community.vectorstores import PGVector
    except ImportError:
        PGVector = None
        logger.warning("PGVector package not found! Please check requirements.txt.")

# Try importing OpenAI embeddings/models
try:
    from langchain_openai import OpenAIEmbeddings, ChatOpenAI
except ImportError:
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
        from langchain_community.chat_models import ChatOpenAI
    except ImportError:
        OpenAIEmbeddings = None
        ChatOpenAI = None
        logger.warning("OpenAI packages not available. Fallback disabled.")

# Try importing Ollama embeddings/models
try:
    from langchain_ollama import OllamaEmbeddings, ChatOllama
except ImportError:
    try:
        from langchain_community.embeddings import OllamaEmbeddings
        from langchain_community.chat_models import ChatOllama
    except ImportError:
        OllamaEmbeddings = None
        ChatOllama = None
        logger.warning("Ollama LangChain integrations not fully available.")

# Import BGE embeddings for high-quality local embeddings
try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    bge_model = SentenceTransformer(settings.BGE_MODEL_NAME)
    reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    logger.info(f"BGE model '{settings.BGE_MODEL_NAME}' and CrossEncoder reranker loaded successfully.")
except Exception as e:
    bge_model = None
    reranker_model = None
    logger.warning(f"Could not load SentenceTransformers models: {e}. Fallback to Ollama embeddings.")

import json
import numpy as np

class InMemoryVectorStore:
    """In-memory vector store for development/testing without database."""
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.store_path = "./data/local_vector_store.json"
        self._load_store()

    def _load_store(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r") as f:
                    self.chunks = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load in-memory vector store: {e}")
                self.chunks = []
        else:
            self.chunks = []

    def _save_store(self):
        try:
            with open(self.store_path, "w") as f:
                json.dump(self.chunks, f)
        except Exception as e:
            logger.error(f"Failed to save in-memory vector store: {e}")

    def add_documents(self, documents: List[LCDocument]):
        if not documents:
            return
        
        texts = [doc.page_content for doc in documents]
        vectors = self.embeddings.embed_documents(texts)
        
        for doc, vector in zip(documents, vectors):
            self.chunks.append({
                "page_content": doc.page_content,
                "metadata": doc.metadata,
                "embedding": vector
            })
            
        self._save_store()
        logger.info(f"Added {len(documents)} chunks to local vector store file.")

    def similarity_search(self, query: str, k: int = 5, filter: dict = None) -> List[LCDocument]:
        if not self.chunks:
            return []
            
        query_vector = self.embeddings.embed_query(query)
        
        filtered_chunks = self.chunks
        if filter:
            filtered_chunks = [
                c for c in self.chunks 
                if all(c["metadata"].get(key) == str(val) for key, val in filter.items())
            ]
            
        if not filtered_chunks:
            return []
            
        results = []
        q_vec = np.array(query_vector)
        q_norm = np.linalg.norm(q_vec)
        
        for c in filtered_chunks:
            c_vec = np.array(c["embedding"])
            c_norm = np.linalg.norm(c_vec)
            if q_norm > 0 and c_norm > 0:
                similarity = np.dot(q_vec, c_vec) / (q_norm * c_norm)
            else:
                similarity = 0.0
            
            results.append((similarity, c))
            
        results.sort(key=lambda x: x[0], reverse=True)
        
        top_k = results[:k]
        return [
            LCDocument(page_content=item[1]["page_content"], metadata=item[1]["metadata"])
            for item in top_k
        ]

class BGEEmbeddings:
    """Wrapper for BGE embeddings via sentence-transformers."""
    def __init__(self, model_name: str = settings.BGE_MODEL_NAME):
        self.model = SentenceTransformer(model_name)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents efficiently in batches."""
        return self.model.encode(texts, batch_size=settings.EMBEDDING_BATCH_SIZE, convert_to_numpy=True).tolist()
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        return self.model.encode(text, convert_to_numpy=True).tolist()

# Helper to resolve Embeddings
def get_embeddings():
    """Get embeddings with priority: BGE > Ollama > OpenAI."""
    try:
        if settings.USE_BGE_EMBEDDING and settings.EMBEDDING_PROVIDER == "bge":
            logger.info(f"Using BGE embeddings: {settings.BGE_MODEL_NAME}")
            return BGEEmbeddings(settings.BGE_MODEL_NAME)
    except Exception as e:
        logger.warning(f"Failed to load BGE embeddings: {e}. Falling back to Ollama.")
    
    if settings.LLM_PROVIDER == "ollama":
        if OllamaEmbeddings is None:
            raise ValueError("OllamaEmbeddings is not available.")
        logger.info(f"Using Ollama embeddings: {settings.OLLAMA_EMBEDDING_MODEL}")
        return OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_EMBEDDING_MODEL
        )
    
    if OpenAIEmbeddings is not None:
        logger.info("Using OpenAI embeddings (fallback)")
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
    
    raise ValueError("No embedding provider available!")

# Helper to resolve LLM with fallback mechanism
def get_llm(force_provider: Optional[str] = None) -> Any:
    """Get LLM with automatic fallback mechanism."""
    primary_provider = force_provider or settings.LLM_PROVIDER
    
    if primary_provider == "ollama":
        try:
            if ChatOllama is None:
                raise ValueError("ChatOllama is not available.")
            logger.info(f"Using Ollama LLM: {settings.OLLAMA_LLM_MODEL}")
            return ChatOllama(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                streaming=settings.LLM_STREAMING
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama LLM: {e}")
            if settings.ENABLE_FALLBACK and settings.LLM_FALLBACK_PROVIDER == "openai":
                logger.info("Falling back to OpenAI LLM")
                return get_llm(force_provider="openai")
            raise
    
    if primary_provider == "openai":
        if ChatOpenAI is None:
            raise ValueError("ChatOpenAI is not available.")
        logger.info(f"Using OpenAI LLM: {settings.OPENAI_MODEL}")
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            streaming=settings.LLM_STREAMING
        )
    
    raise ValueError(f"Unknown LLM provider: {primary_provider}")

# Helper to resolve Vector Store
def get_vector_store():
    embeddings = get_embeddings()
    if not USE_POSTGRES:
        logger.info("Using InMemoryVectorStore fallback...")
        return InMemoryVectorStore(embeddings)
        
    if PGVector is None:
        raise ValueError("PGVector store is not initialized properly.")
    
    conn_url = settings.DATABASE_SYNC_URL
    
    return PGVector(
        embeddings=embeddings,
        collection_name="clinical_docs_collection",
        connection=conn_url,
        use_jsonb=True
    )

# PDF parser that combines text and pdfplumber tables
def parse_pdf(file_path: str) -> Tuple[List[str], int]:
    logger.info(f"Starting parsing of PDF: {file_path}")
    
    # 1. Extract text using pypdf
    reader = PdfReader(file_path)
    page_count = len(reader.pages)
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    
    # 2. Extract tables using pdfplumber
    tables_by_page = {}
    try:
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    formatted_tables = []
                    for table in tables:
                        markdown_rows = []
                        for row in table:
                            clean_row = [str(cell or "").replace("\n", " ").strip() for cell in row]
                            if not any(clean_row):
                                continue
                            markdown_rows.append("| " + " | ".join(clean_row) + " |")
                        
                        if markdown_rows:
                            num_cols = len(table[0]) if table else 0
                            if num_cols > 0:
                                sep = "| " + " | ".join(["---"] * num_cols) + " |"
                                markdown_rows.insert(1, sep)
                            formatted_tables.append("\n".join(markdown_rows))
                    
                    if formatted_tables:
                        tables_by_page[idx] = formatted_tables
    except Exception as ex:
        logger.warning(f"pdfplumber table extraction failed: {ex}. Falling back to plain text.")

    # 3. Merge text and tables
    final_pages = []
    for idx, raw_text in enumerate(pages_text):
        content = raw_text.strip()
        if idx in tables_by_page and tables_by_page[idx]:
            content += "\n\n### Extracted Structured Table Data:\n" + "\n\n".join(tables_by_page[idx])
        final_pages.append(content)
        
    return final_pages, page_count

# Async Ingestion Task
async def ingest_document_async(document_id: str, experiment_id: str, file_path: str, filename: str):
    logger.info(f"Ingestion started for document_id={document_id}, experiment_id={experiment_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            # Update status to processing
            await db.execute(
                update(DBDocument)
                .where(DBDocument.id == document_id)
                .values(status="processing")
            )
            await db.commit()
            
            # Parse PDF in thread pool
            pages_content, page_count = await asyncio.to_thread(parse_pdf, file_path)
            
            # Create LangChain Document objects
            documents = []
            for idx, page_text in enumerate(pages_content):
                if not page_text.strip():
                    continue
                doc = LCDocument(
                    page_content=page_text,
                    metadata={
                        "experiment_id": str(experiment_id),
                        "document_id": str(document_id),
                        "filename": filename,
                        "page_number": idx + 1
                    }
                )
                documents.append(doc)
            
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "]
            )
            chunks = await asyncio.to_thread(text_splitter.split_documents, documents)
            logger.info(f"Split PDF into {len(chunks)} chunks.")
            
            # Add to vector store
            vector_store = get_vector_store()
            
            if chunks:
                batch_size = settings.EMBEDDING_BATCH_SIZE
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    await asyncio.to_thread(vector_store.add_documents, batch)
            
            # Update status to ready and update page count
            await db.execute(
                update(DBDocument)
                .where(DBDocument.id == document_id)
                .values(status="ready", page_count=page_count)
            )
            await db.commit()
            logger.info(f"Ingestion completed successfully for document_id={document_id}")
            
        except Exception as e:
            logger.error(f"Error during ingestion of document_id={document_id}: {e}", exc_info=True)
            await db.execute(
                update(DBDocument)
                .where(DBDocument.id == document_id)
                .values(status="error")
            )
            await db.commit()

# Reranking helper using CrossEncoder
def rerank_documents(query: str, documents: List[LCDocument], top_n: int = 5) -> List[LCDocument]:
    if not reranker_model or not documents:
        return documents[:top_n]
    
    pairs = [[query, doc.page_content] for doc in documents]
    scores = reranker_model.predict(pairs)
    
    scored_docs = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
    
    return [doc for score, doc in scored_docs[:top_n]]

# Retrieve contexts from vector store with metadata filtering
def retrieve_contexts(query: str, experiment_ids: List[str], top_k: int = 15, top_n: int = 5) -> List[LCDocument]:
    vector_store = get_vector_store()
    
    all_retrieved = []
    for exp_id in experiment_ids:
        filter_dict = {"experiment_id": str(exp_id)}
        results = vector_store.similarity_search(query, k=top_k, filter=filter_dict)
        all_retrieved.extend(results)
    
    # De-duplicate results
    seen = set()
    unique_retrieved = []
    for doc in all_retrieved:
        fingerprint = (doc.page_content, doc.metadata.get("document_id"), doc.metadata.get("page_number"))
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_retrieved.append(doc)
            
    # Apply Reranker
    reranked = rerank_documents(query, unique_retrieved, top_n=top_n)
    return reranked
