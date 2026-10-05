"""
RAG / knowledge-base layer (Member 2).

Ingestion (DOCX §4.3 / §7.4):
    document → extraction → cleaning → chunking → metadata → embedding
    → vector store (one per agent KB + a separate Canonical KB) → retrieval

Entry points
------------
    python -m src.rag.build            # ingest knowledge_base/sources → knowledge_base/<kb>/
    python -m src.rag.retrieval_demo   # one retrieval test per agent
    from src.rag.registry import build_registry      # live KBRegistry for Pipeline
    from src.rag.interface import run_agent          # chunk + agent id → AgentFinding
"""
