"""Memory implementations: in-process + persistent, with hybrid ranking + reflection."""

from .embedding import HashingEmbedding, LiteLLMEmbedding
from .inmemory import InMemoryMemory
from .jsonfile import JsonFileMemory
from .pgvector import PgVectorMemory  # lazy-imports psycopg; safe to import here
from .ranking import bm25_score, hybrid_rank, rrf_fuse, tokenize
from .reflection import LLMReflector
from .rerank import LexicalOverlapReranker
from .types import MemoryType, lesson_record

__all__ = [
    "InMemoryMemory",
    "JsonFileMemory",
    "PgVectorMemory",
    "LLMReflector",
    "HashingEmbedding",
    "LiteLLMEmbedding",
    "LexicalOverlapReranker",
    "MemoryType",
    "lesson_record",
    "hybrid_rank",
    "tokenize",
    "bm25_score",
    "rrf_fuse",
]
