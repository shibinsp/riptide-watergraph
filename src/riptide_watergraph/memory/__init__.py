"""Memory implementations: in-process + persistent, with hybrid ranking + reflection."""

from .consolidation import ConsolidationReport, consolidate_memory
from .embedding import HashingEmbedding, LiteLLMEmbedding
from .extraction import LLMTripleExtractor, RuleTripleExtractor
from .inmemory import InMemoryMemory
from .jsonfile import JsonFileMemory
from .knowledge_graph import KnowledgeGraph
from .pgvector import PgVectorMemory  # lazy-imports psycopg; safe to import here
from .ranking import bm25_score, hybrid_rank, rrf_fuse, tokenize
from .reflection import LLMReflector
from .rerank import LexicalOverlapReranker
from .types import MemoryType, fact_record, lesson_record

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
    "fact_record",
    "hybrid_rank",
    "tokenize",
    "bm25_score",
    "rrf_fuse",
    # cognitive memory: knowledge graph + consolidation sleep cycle
    "KnowledgeGraph",
    "RuleTripleExtractor",
    "LLMTripleExtractor",
    "consolidate_memory",
    "ConsolidationReport",
]
