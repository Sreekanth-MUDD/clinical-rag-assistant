import os
import uuid
import json
import logging
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse
from langchain_core.messages import SystemMessage, HumanMessage

from app.database import get_db, init_db, User, Document as DBDocument, ChatMessage
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.schemas import UserCreate, UserLogin, Token, DocumentResponse, ChatQueryRequest, ChatMessageResponse, ChatHistoryResponse
from app.services import ingest_document_async, retrieve_contexts, get_llm, delete_document_embeddings_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RCG Scientific Assistant API", version="1.0.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup DB Init
@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database and tables...")
    await init_db()
    logger.info("Database initialized.")

# Auth Routes
@app.post("/api/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_password = get_password_hash(user_in.password)
    new_user = User(username=user_in.username, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": new_user.username
    }

@app.post("/api/auth/login", response_model=Token)
async def login(user_in: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == user_in.username))
    user = result.scalars().first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username
    }

# Document Routes
@app.get("/api/documents", response_model=List[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DBDocument)
        .where(DBDocument.user_id == current_user.id)
        .order_by(DBDocument.created_at.desc())
    )
    documents = result.scalars().all()
    return documents

@app.post("/api/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported for now.")

    # Generate unique filename on disk
    file_id = str(uuid.uuid4())
    filename_on_disk = f"{file_id}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename_on_disk)
    
    # Save file
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write file to disk: {e}")
        raise HTTPException(status_code=500, detail="Could not write file to storage.")

    # Create document record
    doc_record = DBDocument(
        id=file_id,
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        status="pending",
        page_count=0
    )
    db.add(doc_record)
    await db.commit()
    await db.refresh(doc_record)

    # Schedule asynchronous ingestion
    background_tasks.add_task(
        ingest_document_async,
        document_id=file_id,
        file_path=file_path,
        filename=file.filename
    )

    return doc_record

@app.delete("/api/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify document exists and belongs to current user
    result = await db.execute(
        select(DBDocument)
        .where(DBDocument.id == document_id, DBDocument.user_id == current_user.id)
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from disk
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            logger.error(f"Failed to remove document file from disk: {e}")
    
    # Delete from database
    await db.delete(document)
    await db.commit()
    
    # Schedule embedding deletion asynchronously
    background_tasks.add_task(
        delete_document_embeddings_async,
        document_id=document_id
    )
    
    return {"detail": "Document deletion scheduled successfully"}

@app.get("/api/documents/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DBDocument)
        .where(DBDocument.id == document_id, DBDocument.user_id == current_user.id)
    )
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": document.id,
        "status": document.status,
        "page_count": document.page_count
    }

# SSE Chat and Query Route (Document-centric)
@app.post("/api/chat/query")
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify document exists and belongs to user
    db_result = await db.execute(
        select(DBDocument)
        .where(DBDocument.id == request.document_id, DBDocument.user_id == current_user.id)
    )
    document = db_result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or access denied")

    # Save user message to chat history
    user_message = ChatMessage(
        document_id=request.document_id,
        user_id=current_user.id,
        role="user",
        content=request.query
    )
    db.add(user_message)
    await db.commit()

    async def event_generator():
        try:
            # 1. Retrieve context chunks scoped by document_id
            contexts = retrieve_contexts(request.query, [request.document_id], top_k=15, top_n=5)
            
            if not contexts:
                yield {
                    "event": "sources",
                    "data": json.dumps([])
                }
                yield {
                    "event": "token",
                    "data": "I couldn't find any relevant clinical documentation in this document to answer your query. Please try rephrasing your question."
                }
                yield {"event": "end", "data": ""}
                return

            # Format source references
            sources = []
            context_str = ""
            for idx, doc in enumerate(contexts):
                filename = doc.metadata.get("filename", "Unknown Document")
                page = doc.metadata.get("page_number", "?")
                snippet = doc.page_content[:250] + "..."
                
                # Check for table section
                is_table = "### Extracted Structured Table Data" in doc.page_content
                content_type = "Table" if is_table else "Text"
                
                sources.append({
                    "filename": filename,
                    "page_number": int(page) if isinstance(page, (int, float)) else page,
                    "content_type": content_type,
                    "content_snippet": snippet
                })
                
                context_str += f"\n[Source {idx+1}] - File: {filename}, Page {page}\nContent:\n{doc.page_content}\n"

            # Yield sources event first
            yield {
                "event": "sources",
                "data": json.dumps(sources)
            }
            
            # 2. System and User Prompt construction
            system_prompt = (
                "You are the RCG Scientific Assistant, an expert in clinical documentation and biostatistics.\n"
                "Your objective is to answer the user's queries using only the provided context chunks from this document.\n"
                "You must cite your sources in the text using bracket format corresponding to the sources, e.g. [Source 1], [Source 2], etc.\n"
                "If the context contains table data (demographics, features, metrics, endpoints), summarize or contrast them clearly.\n"
                "If you cannot find the answer in the provided document, state clearly: 'Based on the provided documentation, I could not find information to answer this query.' Do not make up answers.\n"
                "Maintain a strictly professional, clinical, and helpful tone."
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Context Document Chunks:\n{context_str}\n\nQuestion: {request.query}")
            ]
            
            # 3. Stream tokens from LLM and build response
            llm = get_llm()
            full_response = ""
            async for chunk in llm.astream(messages):
                full_response += chunk.content
                yield {
                    "event": "token",
                    "data": chunk.content
                }
                
            yield {"event": "end", "data": ""}

            # Save assistant message to chat history
            assistant_message = ChatMessage(
                document_id=request.document_id,
                user_id=current_user.id,
                role="assistant",
                content=full_response,
                sources=sources
            )
            db.add(assistant_message)
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error in chat SSE streaming: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": f"Internal assistant error: {str(e)}"
            }
            yield {"event": "end", "data": ""}

    return EventSourceResponse(event_generator())

# Chat History Routes
@app.get("/api/documents/{document_id}/chat-history", response_model=ChatHistoryResponse)
async def get_chat_history(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify document exists and belongs to user
    db_result = await db.execute(
        select(DBDocument)
        .where(DBDocument.id == document_id, DBDocument.user_id == current_user.id)
    )
    document = db_result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or access denied")

    # Get chat history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.document_id == document_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    return ChatHistoryResponse(
        document_id=document_id,
        messages=messages
    )
