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

# Experiment Schemas
class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1)
    disease_area: str = Field(..., min_length=1)
    model_type: str = Field(..., min_length=1)

class ExperimentResponse(BaseModel):
    id: str
    name: str
    disease_area: str
    model_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Document Schemas
class DocumentResponse(BaseModel):
    id: str
    experiment_id: str
    filename: str
    status: str
    page_count: int
    created_at: datetime

    class Config:
        from_attributes = True

# Chat Schemas
class ChatQueryRequest(BaseModel):
    query: str
    experiment_ids: List[str]
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

class CompareRequest(BaseModel):
    query: str
    experiment_ids: List[str]

class CompareResponse(BaseModel):
    comparison: str
    sources: List[ChatSource]
