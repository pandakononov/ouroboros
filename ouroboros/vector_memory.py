"""
Ouroboros — Vector Memory System.

Multi-store semantic memory backed by ChromaDB + Ollama embeddings.
Four stores mirror cognitive memory architecture:
  - episodic:   events, conversations, what happened (chronological)
  - semantic:   facts, knowledge, entities (what I know)
  - procedural: learned patterns, workflows (how to do things)
  - vault:      pinned memories, never forgotten

All stores share a single ChromaDB instance on local disk.
Embeddings via local Ollama (nomic-embed-text).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings

log = logging.getLogger(__name__)

# Store types
STORES = ("episodic", "semantic", "procedural", "vault")

# Decay weights per store (vault = infinite, never decays)
STORE_WEIGHTS = {
    "episodic": 0.8,
    "semantic": 1.2,
    "procedural": 1.0,
    "vault": float("inf"),
}


class VectorMemory:
    """Multi-store vector memory with ChromaDB backend."""

    def __init__(
        self,
        data_dir: str = "",
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
    ):
        self._data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "local_data", "chromadb"
        )
        self._ollama_url = ollama_url
        self._embed_model = embed_model
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: Dict[str, Any] = {}

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            os.makedirs(self._data_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self._data_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            log.info(f"ChromaDB initialized at {self._data_dir}")
        return self._client

    def _get_collection(self, store: str):
        if store not in self._collections:
            client = self._get_client()
            self._collections[store] = client.get_or_create_collection(
                name=f"ouroboros_{store}",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[store]

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings from local Ollama."""
        import requests

        results = []
        for text in texts:
            try:
                resp = requests.post(
                    f"{self._ollama_url}/api/embed",
                    json={"model": self._embed_model, "input": text},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embeddings", [[]])[0]
                results.append(embedding)
            except Exception as e:
                log.warning(f"Embedding failed: {e}")
                # Return zero vector as fallback
                results.append([0.0] * 768)
        return results

    def _make_id(self, text: str, store: str) -> str:
        """Generate deterministic ID from content."""
        h = hashlib.md5(f"{store}:{text[:500]}".encode()).hexdigest()
        return f"{store}_{h[:12]}"

    # ── Write operations ──────────────────────────────────────────────

    def remember(
        self,
        text: str,
        store: str = "semantic",
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "agent",
        dedup_threshold: float = 0.95,
    ) -> str:
        """Store a memory in the specified store with semantic dedup.

        If a memory with >dedup_threshold similarity exists, updates it
        instead of creating a duplicate.

        Returns the memory ID.
        """
        if store not in STORES:
            store = "semantic"

        collection = self._get_collection(store)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        embeddings = self._embed([text])

        # Semantic dedup: check if near-duplicate exists
        if collection.count() > 0 and dedup_threshold < 1.0:
            try:
                search = collection.query(
                    query_embeddings=embeddings,
                    n_results=1,
                    include=["documents", "metadatas", "distances"],
                )
                if search["distances"][0]:
                    distance = search["distances"][0][0]
                    similarity = 1.0 - (distance / 2.0)
                    if similarity >= dedup_threshold:
                        # Update existing memory instead of creating duplicate
                        existing_id = search["ids"][0][0]
                        existing_meta = search["metadatas"][0][0]
                        existing_meta["last_accessed"] = now
                        existing_meta["access_count"] = str(int(existing_meta.get("access_count", 1)) + 1)
                        # Merge text if substantially different
                        existing_doc = search["documents"][0][0]
                        if len(text) > len(existing_doc) * 1.2:
                            # New text is significantly longer — replace
                            collection.update(
                                ids=[existing_id],
                                documents=[text],
                                embeddings=embeddings,
                                metadatas=[existing_meta],
                            )
                        else:
                            collection.update(ids=[existing_id], metadatas=[existing_meta])
                        log.info(f"[memory] dedup: updated existing {existing_id} (sim={similarity:.2f})")
                        return existing_id
            except Exception:
                pass  # Dedup failed, proceed with new entry

        mem_id = self._make_id(text, store)

        meta = {
            "store": store,
            "source": source,
            "created_at": now,
            "last_accessed": now,
            "access_count": 1,
            "decay_score": 1.0,
        }
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})

        collection.upsert(
            ids=[mem_id],
            embeddings=embeddings,
            documents=[text],
            metadatas=[meta],
        )

        log.info(f"[memory] stored in {store}: {text[:80]}...")
        return mem_id

    def remember_episode(self, text: str, metadata: Optional[Dict] = None) -> str:
        """Store an episodic memory (event, conversation moment)."""
        meta = metadata or {}
        meta["date"] = datetime.date.today().isoformat()
        return self.remember(text, store="episodic", metadata=meta, source="episode")

    def remember_fact(self, text: str, metadata: Optional[Dict] = None) -> str:
        """Store a semantic memory (fact, knowledge)."""
        return self.remember(text, store="semantic", metadata=metadata, source="fact")

    def remember_procedure(self, text: str, metadata: Optional[Dict] = None) -> str:
        """Store a procedural memory (learned pattern)."""
        return self.remember(text, store="procedural", metadata=metadata, source="procedure")

    def pin(self, text: str, metadata: Optional[Dict] = None) -> str:
        """Store in vault (never forgotten)."""
        return self.remember(text, store="vault", metadata=metadata, source="pinned")

    # ── Read operations ───────────────────────────────────────────────

    def recall(
        self,
        query: str,
        stores: Optional[List[str]] = None,
        top_k: int = 10,
        min_score: float = 0.3,
        use_hybrid_score: bool = True,
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories across stores.

        Uses hybrid scoring: semantic_similarity × decay_relevance.
        This ensures fresh memories rank higher than stale but topically similar ones.

        Returns list of {text, store, score, metadata} sorted by hybrid relevance.
        """
        import math as _math

        if stores is None:
            stores = list(STORES)

        query_embedding = self._embed([query])[0]
        results = []
        now = time.time()

        for store in stores:
            try:
                collection = self._get_collection(store)
                if collection.count() == 0:
                    continue

                search = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k * 2, collection.count()),  # fetch more, filter later
                    include=["documents", "metadatas", "distances"],
                )

                for i, doc in enumerate(search["documents"][0]):
                    distance = search["distances"][0][i]
                    # ChromaDB cosine distance: 0 = identical, 2 = opposite
                    semantic_score = 1.0 - (distance / 2.0)
                    if semantic_score < min_score * 0.7:  # loose filter, hybrid will tighten
                        continue

                    meta = search["metadatas"][0][i]

                    if use_hybrid_score:
                        # Lazy decay: calculate freshness on the fly
                        created = meta.get("last_accessed", meta.get("created_at", ""))
                        days_old = 30.0  # default
                        if created:
                            try:
                                from datetime import datetime as _dt, timezone as _tz
                                created_dt = _dt.fromisoformat(created.replace("Z", "+00:00"))
                                days_old = (now - created_dt.timestamp()) / 86400
                            except (ValueError, TypeError):
                                pass

                        access_count = int(meta.get("access_count", 1))
                        store_weight = STORE_WEIGHTS.get(store, 1.0)
                        if store_weight == float("inf"):
                            decay_factor = 1.0  # vault never decays
                        else:
                            decay_factor = _math.exp(-0.03 * days_old) * _math.log2(access_count + 1) * store_weight
                            decay_factor = min(1.0, max(0.01, decay_factor))

                        hybrid_score = semantic_score * decay_factor
                    else:
                        hybrid_score = semantic_score

                    if hybrid_score < min_score:
                        continue

                    # Update access metadata (lazy touch)
                    meta["last_accessed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    meta["access_count"] = str(int(meta.get("access_count", 0)) + 1)
                    try:
                        collection.update(ids=[search["ids"][0][i]], metadatas=[meta])
                    except Exception:
                        pass

                    results.append({
                        "text": doc,
                        "store": store,
                        "score": round(hybrid_score, 3),
                        "semantic_score": round(semantic_score, 3),
                        "id": search["ids"][0][i],
                        "metadata": meta,
                    })
            except Exception as e:
                log.warning(f"[memory] recall from {store} failed: {e}")

        # Sort by hybrid score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def recall_text(self, query: str, top_k: int = 5, min_score: float = 0.3) -> str:
        """Recall memories and format as text for LLM context."""
        memories = self.recall(query, top_k=top_k, min_score=min_score)
        if not memories:
            return "(no relevant memories found)"

        lines = []
        for m in memories:
            store_emoji = {"episodic": "📅", "semantic": "💡", "procedural": "⚙️", "vault": "📌"}.get(m["store"], "🧠")
            lines.append(f"{store_emoji} [{m['store']}] (score: {m['score']}) {m['text']}")
        return "\n".join(lines)

    # ── Forget operations ─────────────────────────────────────────────

    def forget(self, memory_id: str, store: str) -> bool:
        """Remove a specific memory by ID."""
        try:
            collection = self._get_collection(store)
            collection.delete(ids=[memory_id])
            log.info(f"[memory] forgot {memory_id} from {store}")
            return True
        except Exception as e:
            log.warning(f"[memory] forget failed: {e}")
            return False

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        """Return memory counts per store."""
        counts = {}
        for store in STORES:
            try:
                counts[store] = self._get_collection(store).count()
            except Exception:
                counts[store] = 0
        counts["total"] = sum(counts.values())
        return counts

    # ── Batch import from chat history ────────────────────────────────

    def import_chat_history(self, chat_log_path: str, max_entries: int = 500) -> int:
        """Import existing chat.jsonl into episodic memory."""
        imported = 0
        try:
            with open(chat_log_path, "r") as f:
                lines = f.readlines()

            # Take last N entries
            for line in lines[-max_entries:]:
                try:
                    entry = json.loads(line)
                    direction = entry.get("direction", "")
                    text = entry.get("text", "")
                    ts = entry.get("ts", "")

                    if not text or len(text) < 20:
                        continue

                    prefix = "User" if direction == "in" else "Ouroboros"
                    memory_text = f"[{ts[:19]}] {prefix}: {text[:500]}"

                    self.remember_episode(memory_text, metadata={
                        "direction": direction,
                        "timestamp": ts,
                    })
                    imported += 1
                except (json.JSONDecodeError, KeyError):
                    continue

            log.info(f"[memory] imported {imported} entries from chat history")
        except Exception as e:
            log.warning(f"[memory] chat import failed: {e}")
        return imported


# ── Module-level singleton ────────────────────────────────────────────

_instance: Optional[VectorMemory] = None


def get_memory(data_dir: str = "") -> VectorMemory:
    """Get or create the global VectorMemory instance."""
    global _instance
    if _instance is None:
        _instance = VectorMemory(data_dir=data_dir)
    return _instance
