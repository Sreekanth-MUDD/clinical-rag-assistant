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
from app.database import Document as DBDocument, AsyncSessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try importing FAISS for reliable vector storage
try:
    from langchain_community.vectorstores import FAISS
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS package not found! Please install faiss-cpu.")

# OpenAI configuration removed (Ollama-only mode)

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

    def delete_document_embeddings(self, document_id: str):
        self.chunks = [c for c in self.chunks if c["metadata"].get("document_id") != str(document_id)]
        self._save_store()
        logger.info(f"Deleted embeddings for document_id={document_id} from local json store.")

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
    """Get embeddings with priority: BGE > Ollama."""
    try:
        if settings.USE_BGE_EMBEDDING and settings.EMBEDDING_PROVIDER == "bge":
            logger.info(f"Using BGE embeddings: {settings.BGE_MODEL_NAME}")
            return BGEEmbeddings(settings.BGE_MODEL_NAME)
    except Exception as e:
        logger.warning(f"Failed to load BGE embeddings: {e}. Falling back to Ollama.")
    
    if OllamaEmbeddings is None:
        raise ValueError("OllamaEmbeddings is not available.")
    logger.info(f"Using Ollama embeddings: {settings.OLLAMA_EMBEDDING_MODEL}")
    return OllamaEmbeddings(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_EMBEDDING_MODEL
    )

# Helper to resolve LLM
def get_llm() -> Any:
    """Get Ollama LLM."""
    if ChatOllama is None:
        raise ValueError("ChatOllama is not available.")
    logger.info(f"Using Ollama LLM: {settings.OLLAMA_LLM_MODEL}")
    return ChatOllama(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        streaming=settings.LLM_STREAMING
    )

# Helper to resolve Vector Store
def get_vector_store():
    embeddings = get_embeddings()
    
    if not FAISS_AVAILABLE:
        logger.warning("FAISS not available, using InMemoryVectorStore fallback...")
        return InMemoryVectorStore(embeddings)
    
    # Use FAISS for reliable vector storage
    faiss_index_path = "./data/faiss_index"
    os.makedirs(os.path.dirname(faiss_index_path), exist_ok=True)
    
    if os.path.exists(faiss_index_path):
        logger.info("Loading existing FAISS index...")
        return FAISS.load_local(faiss_index_path, embeddings, allow_dangerous_deserialization=True)
    else:
        logger.info("Creating new FAISS index...")
        return FAISS.from_texts([""], embeddings)

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
async def ingest_document_async(document_id: str, file_path: str, filename: str):
    logger.info(f"Ingestion started for document_id={document_id}")
    
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
            logger.info(f"Parsing PDF for document_id={document_id}")
            pages_content, page_count = await asyncio.to_thread(parse_pdf, file_path)
            logger.info(f"Parsed {page_count} pages for document_id={document_id}")
            
            # Create LangChain Document objects
            documents = []
            for idx, page_text in enumerate(pages_content):
                if not page_text.strip():
                    continue
                doc = LCDocument(
                    page_content=page_text,
                    metadata={
                        "document_id": str(document_id),
                        "filename": filename,
                        "page_number": idx + 1
                    }
                )
                documents.append(doc)
            
            # Split documents into chunks
            logger.info(f"Splitting documents into chunks for document_id={document_id}")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
                separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "]
            )
            chunks = await asyncio.to_thread(text_splitter.split_documents, documents)
            logger.info(f"Split PDF into {len(chunks)} chunks for document_id={document_id}")
            
            # Add to vector store with progress tracking
            logger.info(f"Starting embedding generation for {len(chunks)} chunks")
            vector_store = get_vector_store()
            
            if chunks:
                batch_size = settings.EMBEDDING_BATCH_SIZE
                total_batches = (len(chunks) + batch_size - 1) // batch_size
                
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    batch_num = (i // batch_size) + 1
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks) for document_id={document_id}")
                    await asyncio.to_thread(vector_store.add_documents, batch)
                    logger.info(f"Completed batch {batch_num}/{total_batches} for document_id={document_id}")
                
                # Save FAISS index after ingestion
                if FAISS_AVAILABLE:
                    faiss_index_path = "./data/faiss_index"
                    await asyncio.to_thread(vector_store.save_local, faiss_index_path)
                    logger.info(f"Saved FAISS index for document_id={document_id}")
            
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

# Async Embedding Deletion Task
async def delete_document_embeddings_async(document_id: str):
    """Delete document embeddings from the active vector store."""
    if FAISS_AVAILABLE:
        # For FAISS, we need to rebuild the index without the deleted document
        # This is a limitation of FAISS - it doesn't support easy deletion
        # For now, we'll just log and skip deletion
        logger.warning(f"FAISS doesn't support easy deletion. Document {document_id} embeddings will remain in index.")
    else:
        vector_store = get_vector_store()
        if isinstance(vector_store, InMemoryVectorStore):
            vector_store.delete_document_embeddings(document_id)

# Reranking helper using CrossEncoder
def rerank_documents(query: str, documents: List[LCDocument], top_n: int = 5) -> List[LCDocument]:
    if not reranker_model or not documents:
        return documents[:top_n]
    
    pairs = [[query, doc.page_content] for doc in documents]
    scores = reranker_model.predict(pairs)
    
    scored_docs = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
    
    return [doc for score, doc in scored_docs[:top_n]]

# Retrieve contexts from vector store with metadata filtering
def retrieve_contexts(query: str, document_ids: List[str] = None, top_k: int = 15, top_n: int = 5) -> List[LCDocument]:
    vector_store = get_vector_store()
    
    if not document_ids:
        # Search across all documents if none are selected
        logger.info("Retrieving contexts scoped to all documents")
        all_retrieved = vector_store.similarity_search(query, k=top_k)
    else:
        logger.info(f"Retrieving contexts scoped to documents: {document_ids}")
        all_retrieved = []
        for doc_id in document_ids:
            filter_dict = {"document_id": str(doc_id)}
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
