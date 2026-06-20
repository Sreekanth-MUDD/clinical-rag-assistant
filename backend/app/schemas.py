from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Auth Schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Document Schemas
class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    page_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# Chat Schemas
class ChatQueryRequest(BaseModel):
    query: str
    document_id: str  # Single document for document-centric chat
    session_id: Optional[str] = None

class ChatSource(BaseModel):
    filename: str
    page_number: int
    section_title: Optional[str] = None
    content_type: str
    content_snippet: str

class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[ChatSource]

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[List[ChatSource]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatHistoryResponse(BaseModel):
    document_id: str
    messages: List[ChatMessageResponse]
