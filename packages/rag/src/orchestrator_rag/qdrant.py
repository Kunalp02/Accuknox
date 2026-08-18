import hashlib
import uuid

from orchestrator_core.config import settings
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)


def org_collection_name(org_id: uuid.UUID) -> str:
    digest = hashlib.sha256(str(org_id).encode()).hexdigest()[:16]
    return f"org_{digest}"


class QdrantStore:
    def __init__(self, url: str | None = None) -> None:
        self.client = AsyncQdrantClient(url=url or settings.qdrant_url)

    async def ensure_collection(self, org_id: uuid.UUID, vector_size: int = 768) -> str:
        name = org_collection_name(org_id)
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        return name

    async def upsert_chunks(
        self,
        org_id: uuid.UUID,
        kb_id: uuid.UUID,
        doc_id: uuid.UUID,
        chunks: list[tuple[int, str, list[float]]],
    ) -> None:
        name = await self.ensure_collection(org_id, len(chunks[0][2]) if chunks else 768)
        points = []
        for idx, text, vector in chunks:
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "org_id": str(org_id),
                        "kb_id": str(kb_id),
                        "doc_id": str(doc_id),
                        "chunk_index": idx,
                        "text": text,
                    },
                )
            )
        if points:
            await self.client.upsert(collection_name=name, points=points)

    async def search(
        self,
        org_id: uuid.UUID,
        kb_ids: list[uuid.UUID],
        query_vector: list[float],
        limit: int = 5,
    ) -> list[dict]:
        name = org_collection_name(org_id)
        collections = await self.client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            return []

        kb_filter = [str(k) for k in kb_ids]
        results = await self.client.search(
            collection_name=name,
            query_vector=query_vector,
            limit=limit,
            query_filter=Filter(
                must=[
                    FieldCondition(key="org_id", match=MatchValue(value=str(org_id))),
                    FieldCondition(key="kb_id", match=MatchAny(any=kb_filter)),
                ]
            ),
        )
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "kb_id": hit.payload.get("kb_id"),
                "doc_id": hit.payload.get("doc_id"),
            }
            for hit in results
        ]
