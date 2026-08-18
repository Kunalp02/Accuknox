import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator_core.config import settings
from orchestrator_core.database import get_session
from orchestrator_core.models import Document, KnowledgeBase
from orchestrator_core.rbac import has_permission

from orchestrator_api.deps import AuthContext, get_auth_context

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: str | None
    embed_model: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int


def _check(auth: AuthContext, permission: str) -> None:
    if auth.is_api_key:
        raise HTTPException(status_code=403, detail="Not allowed for API keys")
    if not auth.role or not has_permission(auth.role, permission):
        raise HTTPException(status_code=403, detail="Permission denied")


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_kbs(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "kb:read")
    result = await session.execute(
        select(KnowledgeBase).where(KnowledgeBase.organization_id == auth.org_id)
    )
    kbs = result.scalars().all()
    return [
        KnowledgeBaseResponse(
            id=str(k.id), name=k.name, description=k.description, embed_model=k.embed_model
        )
        for k in kbs
    ]


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
async def create_kb(
    body: KnowledgeBaseCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "kb:write")
    kb = KnowledgeBase(
        organization_id=auth.org_id,
        name=body.name,
        description=body.description,
        embed_model=settings.embed_model,
    )
    session.add(kb)
    await session.commit()
    await session.refresh(kb)
    return KnowledgeBaseResponse(
        id=str(kb.id), name=kb.name, description=kb.description, embed_model=kb.embed_model
    )


@router.post("/{kb_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    kb_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
    file: UploadFile = File(...),
):
    _check(auth, "kb:write")
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.organization_id == auth.org_id
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    content = await file.read()
    storage_path = f"{auth.org_id}/{kb_id}/{file.filename}"

    doc = Document(
        organization_id=auth.org_id,
        knowledge_base_id=kb_id,
        filename=file.filename or "upload.txt",
        storage_path=storage_path,
        status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Store locally for dev (MinIO integration can replace this)
    import os

    local_dir = f"/tmp/orchestrator_docs/{auth.org_id}/{kb_id}"
    os.makedirs(local_dir, exist_ok=True)
    local_path = f"{local_dir}/{doc.id}_{file.filename}"
    with open(local_path, "wb") as f:
        f.write(content)
    doc.storage_path = local_path
    await session.commit()

    from arq import create_pool
    from arq.connections import RedisSettings

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    pool = await create_pool(redis_settings)
    await pool.enqueue_job("index_document", str(doc.id))
    await pool.aclose()

    return DocumentResponse(
        id=str(doc.id), filename=doc.filename, status=doc.status, chunk_count=doc.chunk_count
    )


@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
):
    _check(auth, "kb:read")
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.organization_id == auth.org_id
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    docs_result = await session.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id, Document.organization_id == auth.org_id)
        .order_by(Document.created_at.desc())
    )
    docs = docs_result.scalars().all()
    return [
        DocumentResponse(
            id=str(d.id), filename=d.filename, status=d.status, chunk_count=d.chunk_count
        )
        for d in docs
    ]
