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

from app.config import settings
from app.database import get_db, init_db, User, Experiment, Document as DBDocument
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.schemas import UserCreate, UserLogin, Token, ExperimentCreate, ExperimentResponse, DocumentResponse, ChatQueryRequest
from app.services import ingest_document_async, retrieve_contexts, get_llm

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

# Experiment Routes
@app.get("/api/experiments", response_model=List[ExperimentResponse])
async def list_experiments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Experiment).order_by(Experiment.created_at.desc()))
    experiments = result.scalars().all()
    return experiments

@app.post("/api/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    experiment_in: ExperimentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_experiment = Experiment(
        name=experiment_in.name,
        disease_area=experiment_in.disease_area,
        model_type=experiment_in.model_type,
        status="completed"
    )
    db.add(new_experiment)
    await db.commit()
    await db.refresh(new_experiment)
    return new_experiment

@app.get("/api/experiments/{experiment_id}/documents", response_model=List[DocumentResponse])
async def list_experiment_documents(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DBDocument)
        .where(DBDocument.experiment_id == experiment_id)
        .order_by(DBDocument.created_at.desc())
    )
    documents = result.scalars().all()
    return documents

# Document Upload Routes
@app.post("/api/experiments/{experiment_id}/upload", response_model=DocumentResponse)
async def upload_document(
    experiment_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify experiment exists
    exp_result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = exp_result.scalars().first()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
        
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
        experiment_id=experiment_id,
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
        experiment_id=experiment_id,
        file_path=file_path,
        filename=file.filename
    )

    return doc_record

@app.get("/api/documents/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(DBDocument).where(DBDocument.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": document.id,
        "status": document.status,
        "page_count": document.page_count
    }

# SSE Chat and Query Route
@app.post("/api/chat/query")
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user)
):
    if not request.experiment_ids:
        raise HTTPException(status_code=400, detail="Must select at least one experiment scope.")

    async def event_generator():
        try:
            # 1. Retrieve context chunks scoped by experiment_ids
            # Query the database to fetch chunks with metadata filter
            # Let's retrieve context
            contexts = retrieve_contexts(request.query, request.experiment_ids, top_k=15, top_n=5)
            
            if not contexts:
                yield {
                    "event": "sources",
                    "data": json.dumps([])
                }
                yield {
                    "event": "token",
                    "data": "I couldn't find any relevant clinical documentation in the selected experiments to answer your query. Please upload documents first or refine your search."
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
                "You are the RCG Scientific Assistant, an expert in clinical documentation and biostatistics at Sanofi.\n"
                "Your objective is to answer the user's queries using only the provided context chunks.\n"
                "You must cite your sources in the text using bracket format corresponding to the sources, e.g. [Source 1], [Source 2], etc.\n"
                "If the context contains table data (demographics, features, metrics, endpoints), summarize or contrast them clearly.\n"
                "If multiple documents are provided in the context, synthesize the findings across them to provide comparative statistics.\n"
                "If you cannot find the answer in the provided documents, state clearly: 'Based on the provided documentation, I could not find information to answer this query.' Do not make up answers.\n"
                "Maintain a strictly professional, clinical, and helpful tone."
            )
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Context Document Chunks:\n{context_str}\n\nQuestion: {request.query}")
            ]
            
            # 3. Stream tokens from LLM
            llm = get_llm()
            async for chunk in llm.astream(messages):
                yield {
                    "event": "token",
                    "data": chunk.content
                }
                
            yield {"event": "end", "data": ""}
            
        except Exception as e:
            logger.error(f"Error in chat SSE streaming: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": f"Internal assistant error: {str(e)}"
            }
            yield {"event": "end", "data": ""}

    return EventSourceResponse(event_generator())
