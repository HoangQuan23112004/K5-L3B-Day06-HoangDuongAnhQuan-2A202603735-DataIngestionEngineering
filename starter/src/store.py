"""Persistent Qdrant local collections with cosine search and payload filters."""
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from qdrant_client import QdrantClient, models
from .models import Chunk


class QdrantStore:
    def __init__(self, path: str | Path, dimensions: int):
        self.client = QdrantClient(path=str(path))
        self.dimensions = dimensions

    def name(self, strategy: str) -> str:
        if strategy not in ('A', 'B', 'C'):
            raise ValueError('Unknown strategy')
        return f'alice_{strategy}'

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not chunks or len(chunks) != len(vectors) or any(len(v) != self.dimensions for v in vectors):
            raise ValueError('Nonempty chunks and compatible vectors required')
        name = self.name(strategy)
        # Replace points in this lab-owned collection, including stale documents.
        # Avoid delete/recreate: Windows may retain an open SQLite handle in local Qdrant.
        # This full refresh is not transactional; a failed refresh must be rerun.
        if self.client.collection_exists(name):
            config = self.client.get_collection(name).config.params.vectors
            if config.size != self.dimensions or config.distance != models.Distance.COSINE:
                raise ValueError('Existing collection has incompatible embedding configuration')
            self.client.delete(name, points_selector=models.FilterSelector(filter=models.Filter()), wait=True)
        else:
            self.client.create_collection(name, vectors_config=models.VectorParams(
                size=self.dimensions, distance=models.Distance.COSINE))
        for offset in range(0, len(chunks), 128):
            self.client.upsert(name, points=[models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, c.chunk_id)), vector=v,
                payload={**c.metadata, **{k: val for k, val in asdict(c).items() if k != 'metadata'}})
                for c, v in zip(chunks[offset:offset + 128], vectors[offset:offset + 128])], wait=True)
        if self.count(strategy) != len(chunks):
            raise RuntimeError('Stored count does not match snapshot')

    def count(self, strategy: str) -> int:
        return self.client.count(self.name(strategy), exact=True).count

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if filters and set(filters) - {'chapter', 'language'}:
            raise ValueError('Only chapter/language filters are allowed')
        conditions = [models.FieldCondition(key=k, match=models.MatchValue(value=v))
                      for k, v in (filters or {}).items()]
        result = self.client.query_points(self.name(strategy), query=query_vector,
            query_filter=models.Filter(must=conditions) if conditions else None,
            limit=top_k, with_payload=True).points
        return [{'chunk_id': p.payload['chunk_id'], 'text': p.payload['text'],
                 'score': p.score, 'metadata': {k: v for k, v in p.payload.items()
                                             if k not in ('chunk_id', 'text')}} for p in result]

    def close(self) -> None:
        self.client.close()
