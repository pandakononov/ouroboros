"""
Memory tools — vector-based semantic memory for Ouroboros.

Tools: memory_store, memory_recall, memory_forget, memory_stats.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.vector_memory import get_memory


def _memory_store(ctx: ToolContext, text: str, store: str = "semantic", source: str = "") -> str:
    """Store a new memory."""
    mem = get_memory()
    mem_id = mem.remember(text, store=store, source=source or "agent")
    stats = mem.stats()
    return json.dumps({
        "status": "stored",
        "id": mem_id,
        "store": store,
        "stats": stats,
    }, ensure_ascii=False)


def _memory_recall(ctx: ToolContext, query: str, stores: str = "", top_k: int = 5) -> str:
    """Recall relevant memories by semantic search."""
    mem = get_memory()
    store_list = [s.strip() for s in stores.split(",") if s.strip()] or None
    results = mem.recall(query, stores=store_list, top_k=top_k)

    if not results:
        return json.dumps({"memories": [], "message": "No relevant memories found."})

    return json.dumps({
        "memories": [
            {
                "text": r["text"][:500],
                "store": r["store"],
                "score": r["score"],
                "id": r["id"],
            }
            for r in results
        ],
        "count": len(results),
    }, ensure_ascii=False, indent=2)


def _memory_forget(ctx: ToolContext, memory_id: str, store: str) -> str:
    """Remove a specific memory."""
    mem = get_memory()
    ok = mem.forget(memory_id, store)
    return json.dumps({"status": "forgotten" if ok else "failed", "id": memory_id})


def _memory_stats(ctx: ToolContext) -> str:
    """Get memory statistics."""
    mem = get_memory()
    return json.dumps(mem.stats(), indent=2)


def _memory_reflect(ctx: ToolContext) -> str:
    """Run a reflection cycle — decay sweep, consolidate, update core memory."""
    from ouroboros.cognitive_memory import (
        build_reflection_context, run_decay_sweep,
        update_core_memory, vault_eviction_check,
        promote_recurring_episodes,
    )

    # 1. Run decay sweep
    decay_stats = run_decay_sweep()

    # 2. Promote recurring episodic themes to semantic
    promoted = promote_recurring_episodes()

    # 3. Check vault size
    vault_evictions = vault_eviction_check()

    # 4. Update MEMORY.md from ChromaDB state
    update_core_memory()

    # 5. Build reflection context
    context = build_reflection_context()

    return json.dumps({
        "status": "reflection_ready",
        "decay_sweep": decay_stats,
        "promoted_to_semantic": len(promoted),
        "vault_eviction_candidates": len(vault_evictions),
        "context_preview": context[:2000] + "...",
        "instruction": "Use this context to write an internal monologue reflection. "
                       "Be genuine, not performative. Write in Russian.",
    }, ensure_ascii=False, indent=2)


def _memory_auto_capture(ctx: ToolContext, text: str, direction: str = "in") -> str:
    """Auto-capture important information from a message."""
    from ouroboros.cognitive_memory import auto_capture, classify_memory

    classification = classify_memory(text)
    mem_id = auto_capture(text, direction=direction)

    return json.dumps({
        "captured": mem_id is not None,
        "id": mem_id,
        "classification": classification,
    }, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("memory_store", {
            "name": "memory_store",
            "description": (
                "Store a memory in vector database. Stores: "
                "'episodic' (events, conversations), "
                "'semantic' (facts, knowledge), "
                "'procedural' (learned patterns, how-to), "
                "'vault' (important, never forget). "
                "Use this to remember important information across sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Memory content to store"},
                    "store": {
                        "type": "string",
                        "enum": ["episodic", "semantic", "procedural", "vault"],
                        "description": "Memory store type",
                    },
                    "source": {"type": "string", "description": "Source/reason for storing"},
                },
                "required": ["text"],
            },
        }, _memory_store),

        ToolEntry("memory_recall", {
            "name": "memory_recall",
            "description": (
                "Search memories by semantic similarity. Returns relevant memories "
                "from all stores ranked by relevance. Use before responding to check "
                "if you have relevant prior knowledge or context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "stores": {
                        "type": "string",
                        "description": "Comma-separated store names to search (empty = all)",
                    },
                    "top_k": {"type": "integer", "description": "Max results (default 5)"},
                },
                "required": ["query"],
            },
        }, _memory_recall),

        ToolEntry("memory_forget", {
            "name": "memory_forget",
            "description": "Remove a specific memory by ID and store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "store": {"type": "string"},
                },
                "required": ["memory_id", "store"],
            },
        }, _memory_forget),

        ToolEntry("memory_stats", {
            "name": "memory_stats",
            "description": "Get memory statistics — count of memories per store.",
            "parameters": {"type": "object", "properties": {}},
        }, _memory_stats),

        ToolEntry("memory_reflect", {
            "name": "memory_reflect",
            "description": (
                "Run a reflection cycle: decay sweep + build reflection context. "
                "Use when user says 'reflect', 'consolidate', or at end of day. "
                "Returns context for writing an internal monologue."
            ),
            "parameters": {"type": "object", "properties": {}},
        }, _memory_reflect),
    ]
