"""
HR Policy Knowledge Retriever.

Queries the local ChromaDB collection to retrieve relevant policy chunks
for a given question. Used by the PolicyExpert agent's @tool function.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..models import PolicyContext

COLLECTION_NAME = "hr_policy"


def query_policy_knowledge(
    question: str,
    k: int = 4,
    chroma_dir: Optional[Path] = None,
    embeddings=None,
) -> PolicyContext:
    """Query the HR policy knowledge base for relevant content.

    Args:
        question: Natural language question about HR policy.
        k: Number of chunks to retrieve.
        chroma_dir: ChromaDB persistence directory. Auto-detected if None.
        embeddings: LangChain embeddings instance. Auto-created if None.

    Returns:
        PolicyContext with retrieved chunks and source filenames.
    """
    import chromadb
    from chromadb.utils.embedding_functions import EmbeddingFunction

    if chroma_dir is None:
        from contoso_hr.config import get_config
        chroma_dir = get_config().chroma_dir

    if embeddings is None:
        from contoso_hr.config import get_config
        embeddings = get_config().get_embeddings()

    class LangChainEmbeddingWrapper(EmbeddingFunction):
        def __init__(self, lc_embeddings):
            self._emb = lc_embeddings

        def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
            return self._emb.embed_documents(input)

    client = chromadb.PersistentClient(path=str(chroma_dir))

    try:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=LangChainEmbeddingWrapper(embeddings),
        )
    except Exception:
        return PolicyContext(
            chunks=[],
            sources=[],
            query=question,
        )

    # Embed the question and query. include=["distances"] gives us cosine
    # distance per match; we invert to similarity for the UI's provenance panel.
    query_embedding = embeddings.embed_query(question)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[str] = []
    sources: list[str] = []
    scores: list[float] = []

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    # ChromaDB returns distances only when explicitly requested via include=.
    # Cosine distance is in [0, 2] but in practice clusters in [0, 1] for our
    # corpus; clamp to [0, 1] to keep the UI score honest.
    distances = results.get("distances", [[]])[0] or []

    for i, (doc, meta) in enumerate(zip(docs, metas)):
        chunks.append(doc)
        sources.append(meta.get("source", "unknown"))
        if i < len(distances):
            sim = max(0.0, min(1.0, 1.0 - float(distances[i])))
            scores.append(sim)

    return PolicyContext(chunks=chunks, sources=sources, scores=scores, query=question)
