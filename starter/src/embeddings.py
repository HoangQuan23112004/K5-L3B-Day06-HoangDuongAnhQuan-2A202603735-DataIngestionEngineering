"""Real CPU embeddings with FastEmbed / ONNX; no mock fallback."""
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2') -> None:
        from fastembed import TextEmbedding
        self.model_name = model_name
        self.model = TextEmbedding(model_name=model_name, threads=4,
            cache_dir=str(Path(__file__).resolve().parents[1] / '.model_cache'))
        self.dimensions = len(self.embed_query('dimension check'))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts, batch_size=32)]

    def embed_query(self, question: str) -> list[float]:
        return next(iter(self.model.query_embed(question))).tolist()
