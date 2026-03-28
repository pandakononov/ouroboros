"""
Ouroboros — Cognitive Memory Engine.

Higher-level memory operations on top of vector_memory.py:
- Trigger detection (remember/forget/reflect keywords)
- Memory routing (classify into episodic/semantic/procedural/vault)
- Decay model (relevance scoring with time-based decay)
- Auto-capture (important moments from conversations)
- Reflection engine (periodic consolidation + self-examination)
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.vector_memory import get_memory, STORES

log = logging.getLogger(__name__)

# ── Trigger keywords ──────────────────────────────────────────────────

REMEMBER_TRIGGERS = {
    "ru": ["запомни", "не забудь", "имей в виду", "важно:", "на будущее", "сохрани"],
    "en": ["remember", "don't forget", "keep in mind", "note that", "important:", "for future reference", "save this"],
}

FORGET_TRIGGERS = {
    "ru": ["забудь", "не важно", "проехали", "отмени", "удали из памяти"],
    "en": ["forget", "never mind", "disregard", "scratch that", "remove from memory"],
}

REFLECT_TRIGGERS = {
    "ru": ["рефлексия", "порефлексируй", "подведи итоги", "что запомнил"],
    "en": ["reflect", "consolidate", "review memories", "what do you remember"],
}

# ── Trigger detection ─────────────────────────────────────────────────

def detect_trigger(text: str) -> Optional[str]:
    """Detect memory trigger in text. Returns 'remember', 'forget', 'reflect', or None."""
    lower = text.lower().strip()

    for lang in ("ru", "en"):
        for trigger in REMEMBER_TRIGGERS[lang]:
            if trigger in lower:
                return "remember"
        for trigger in FORGET_TRIGGERS[lang]:
            if trigger in lower:
                return "forget"
        for trigger in REFLECT_TRIGGERS[lang]:
            if trigger in lower:
                return "reflect"
    return None


# ── Memory routing (classify store) ──────────────────────────────────

def classify_memory(text: str, context: str = "") -> Dict[str, Any]:
    """Classify memory into appropriate store.

    Uses heuristics first (fast), falls back to LLM for ambiguous cases.
    Key distinction: episodic = time-bound event, semantic = timeless fact.
    "Python лучше JS для этой задачи" → semantic (it's a learned fact)
    "Сегодня решили использовать Python" → episodic (time-bound event)

    Returns: {store, tags, confidence, core_update}
    """
    lower = text.lower()

    # Vault indicators (explicit user request to pin)
    if any(w in lower for w in ["важно", "никогда не забывай", "critical", "important", "vault", "закрепи"]):
        return {"store": "vault", "tags": ["pinned"], "confidence": "high", "core_update": True}

    # Procedural indicators (how-to, steps, workflows)
    if any(w in lower for w in ["как сделать", "how to", "workflow", "процедура", "алгоритм", "шаги", "steps", "рецепт"]):
        return {"store": "procedural", "tags": ["workflow"], "confidence": "high", "core_update": False}

    # Episodic indicators (time-bound: dates, meetings, "today", "happened")
    has_time = any(w in lower for w in [
        "сегодня", "вчера", "завтра", "только что", "произошло", "случилось",
        "встреча", "событие", "решили", "договорились",
        "today", "yesterday", "tomorrow", "just now", "happened", "meeting",
        "decided", "agreed",
    ])

    # Semantic indicators (timeless facts, preferences, knowledge)
    has_fact = any(w in lower for w in [
        "лучше", "хуже", "предпочитаю", "всегда", "никогда", "обычно",
        "потому что", "означает", "является", "это ",
        "better", "worse", "prefer", "always", "never", "usually",
        "because", "means", "is a",
    ])

    if has_time and not has_fact:
        return {"store": "episodic", "tags": ["event"], "confidence": "high", "core_update": False}

    if has_fact and not has_time:
        return {"store": "semantic", "tags": ["fact"], "confidence": "high", "core_update": False}

    if has_time and has_fact:
        # Ambiguous: "Сегодня решили что Python лучше" — both time-bound AND a fact
        # Store in BOTH: episodic (the event) + semantic (the learned fact)
        return {"store": "semantic", "tags": ["fact", "decision"], "confidence": "medium",
                "core_update": False, "also_episodic": True}

    # Default: semantic
    return {"store": "semantic", "tags": ["general"], "confidence": "low", "core_update": False}


# ── Auto-capture from conversations ──────────────────────────────────

# Patterns that indicate something worth remembering
AUTO_CAPTURE_PATTERNS = [
    # User preferences
    r"(?:я |мне |мое |my |i )(?:предпочитаю|нравится|хочу|prefer|like|want)",
    # Decisions
    r"(?:решили|решение|давай |let's |decided|decision)",
    # Important facts
    r"(?:кстати|между прочим|by the way|btw|fun fact)",
    # Names and introductions
    r"(?:меня зовут|my name is|i'm called)",
    # Deadlines and dates
    r"(?:до |к |deadline|before|by |until )\d",
]

_auto_capture_compiled = [re.compile(p, re.IGNORECASE) for p in AUTO_CAPTURE_PATTERNS]


def should_auto_capture(text: str) -> bool:
    """Check if a message should be auto-captured to memory."""
    if len(text) < 30:
        return False
    return any(p.search(text) for p in _auto_capture_compiled)


def auto_capture(text: str, direction: str = "in", timestamp: str = "") -> Optional[str]:
    """Auto-capture a message to appropriate memory store if it matches patterns.

    Handles dual-store for ambiguous cases (also_episodic flag).
    Returns memory_id if captured, None otherwise.
    """
    if not should_auto_capture(text):
        return None

    mem = get_memory()
    prefix = "User" if direction == "in" else "Ouroboros"
    ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
    memory_text = f"[{ts[:19]}] {prefix}: {text[:500]}"

    classification = classify_memory(text)
    mem_id = mem.remember(
        memory_text,
        store=classification["store"],
        metadata={"auto_captured": "true", "direction": direction},
        source="auto_capture",
    )

    # Dual-store: also store in episodic if it's a time-bound decision
    if classification.get("also_episodic"):
        mem.remember(
            memory_text,
            store="episodic",
            metadata={"auto_captured": "true", "direction": direction, "linked_to": mem_id},
            source="auto_capture_dual",
        )

    log.info(f"[cognitive] auto-captured to {classification['store']}: {text[:60]}...")
    return mem_id


# ── Vault management ���────────────────────────────────────────────────

VAULT_MAX_SIZE = 100  # Hard cap on vault entries

def vault_eviction_check() -> List[str]:
    """Check vault size and suggest evictions if over limit.

    Returns list of candidate IDs for eviction (oldest, lowest access).
    Auto-capture cannot write to vault — only explicit user pin can.
    """
    mem = get_memory()
    try:
        collection = mem._get_collection("vault")
        count = collection.count()
        if count <= VAULT_MAX_SIZE:
            return []

        # Get all vault entries sorted by access count (ascending)
        results = collection.get(include=["metadatas"])
        entries = []
        for i, meta in enumerate(results["metadatas"]):
            entries.append({
                "id": results["ids"][i],
                "access_count": int(meta.get("access_count", 1)),
                "created_at": meta.get("created_at", ""),
            })

        # Sort by access count ascending, then by age descending
        entries.sort(key=lambda e: (e["access_count"], e["created_at"]))

        # Suggest bottom 20% for eviction
        evict_count = count - VAULT_MAX_SIZE + 10  # evict enough + buffer
        return [e["id"] for e in entries[:evict_count]]

    except Exception as e:
        log.warning(f"[cognitive] vault eviction check failed: {e}")
        return []


# ── Decay model ──────────────────────────────────────────────────────

DECAY_LAMBDA = 0.03  # ~23 day half-life
ARCHIVE_THRESHOLD = 0.05

def calculate_decay(
    base_score: float,
    days_since_access: float,
    access_count: int,
    store: str,
) -> float:
    """Calculate memory relevance with exponential decay.

    relevance(t) = base × e^(-λ × days) × log2(access_count + 1) × type_weight
    """
    from ouroboros.vector_memory import STORE_WEIGHTS

    weight = STORE_WEIGHTS.get(store, 1.0)
    if weight == float("inf"):
        return 1.0  # Vault never decays

    decay = base_score * math.exp(-DECAY_LAMBDA * days_since_access)
    access_boost = math.log2(access_count + 1)
    relevance = decay * access_boost * weight

    return min(1.0, max(0.0, relevance))


def run_decay_sweep() -> Dict[str, int]:
    """Run decay calculation across all memories, update scores.

    Returns counts: {updated, archived, total}.
    """
    mem = get_memory()
    stats = {"updated": 0, "archived": 0, "total": 0}
    now = datetime.datetime.now(datetime.timezone.utc)

    for store in STORES:
        try:
            collection = mem._get_collection(store)
            if collection.count() == 0:
                continue

            # Get all entries
            all_data = collection.get(include=["metadatas"])

            for i, meta in enumerate(all_data["metadatas"]):
                stats["total"] += 1

                # Calculate days since last access
                last_accessed = meta.get("last_accessed", meta.get("created_at", ""))
                if last_accessed:
                    try:
                        last_dt = datetime.datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
                        days = (now - last_dt).total_seconds() / 86400
                    except (ValueError, TypeError):
                        days = 30  # Default if parse fails
                else:
                    days = 30

                access_count = int(meta.get("access_count", 1))
                base_score = float(meta.get("decay_score", 1.0))

                new_score = calculate_decay(base_score, days, access_count, store)

                # Update metadata
                meta["decay_score"] = str(round(new_score, 4))
                collection.update(
                    ids=[all_data["ids"][i]],
                    metadatas=[meta],
                )
                stats["updated"] += 1

                if new_score < ARCHIVE_THRESHOLD:
                    stats["archived"] += 1

        except Exception as e:
            log.warning(f"[cognitive] decay sweep failed for {store}: {e}")

    log.info(f"[cognitive] decay sweep: {stats}")
    return stats


# ── Reflection engine ────────────────────────────────────────────────

def build_reflection_context(max_tokens: int = 30000) -> str:
    """Build context for reflection from memory stores.

    Reads: MEMORY.md, recent episodes, high-decay entities, scratchpad.
    """
    mem = get_memory()
    sections = []

    # Core memory
    core_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "local_data", "memory", "MEMORY.md"
    )
    if os.path.exists(core_path):
        with open(core_path) as f:
            sections.append("## Core Memory\n" + f.read())

    # Soul
    soul_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "local_data", "memory", "SOUL.md"
    )
    if os.path.exists(soul_path):
        with open(soul_path) as f:
            sections.append("## Soul\n" + f.read())

    # Recent episodic memories (last 50)
    try:
        collection = mem._get_collection("episodic")
        if collection.count() > 0:
            results = collection.get(
                include=["documents", "metadatas"],
                limit=50,
            )
            episodes = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                episodes.append(f"- {doc[:200]}")
            if episodes:
                sections.append("## Recent Episodes\n" + "\n".join(episodes[-30:]))
    except Exception:
        pass

    # Semantic memories (top by decay score)
    try:
        collection = mem._get_collection("semantic")
        if collection.count() > 0:
            results = collection.get(include=["documents", "metadatas"])
            facts = []
            for doc, meta in zip(results["documents"], results["metadatas"]):
                score = float(meta.get("decay_score", 0.5))
                if score > 0.3:
                    facts.append(f"- [{score:.2f}] {doc[:200]}")
            if facts:
                sections.append("## Active Knowledge\n" + "\n".join(facts[:20]))
    except Exception:
        pass

    # Procedural memories
    try:
        collection = mem._get_collection("procedural")
        if collection.count() > 0:
            results = collection.get(include=["documents"])
            procs = [f"- {doc[:200]}" for doc in results["documents"]]
            if procs:
                sections.append("## Learned Procedures\n" + "\n".join(procs[:10]))
    except Exception:
        pass

    # Vault (pinned)
    try:
        collection = mem._get_collection("vault")
        if collection.count() > 0:
            results = collection.get(include=["documents"])
            pinned = [f"- 📌 {doc[:200]}" for doc in results["documents"]]
            if pinned:
                sections.append("## Vault (Never Forget)\n" + "\n".join(pinned))
    except Exception:
        pass

    return "\n\n".join(sections)


# ── Contextual recall ─────────────────────────────────────────────────

def contextual_recall(
    message_text: str,
    fallback_context: str = "",
    top_k: int = 5,
    min_message_len: int = 30,
) -> str:
    """Recall memories relevant to the current incoming message.

    For short/ambiguous messages ("окей", "продолжай"), falls back to
    scratchpad/recent context as query to avoid mushy recall.

    Args:
        message_text: current user message
        fallback_context: scratchpad or last N tokens of dialog (used if message too short)
        top_k: max memories to return
        min_message_len: messages shorter than this use fallback
    """
    mem = get_memory()

    # Short or ambiguous messages → use fallback context
    query = message_text
    if not query or len(query.strip()) < min_message_len:
        if fallback_context:
            query = fallback_context[:500]
        else:
            return ""  # Nothing to query with

    return mem.recall_text(query, top_k=top_k, min_score=0.35)


# ── Episodic → Semantic promotion ────────────────────────────────────

PROMOTION_THRESHOLD = 3  # If a topic appears 3+ times in episodes, promote to semantic

def promote_recurring_episodes() -> List[str]:
    """Find recurring themes in episodic memory and promote to semantic.

    Clusters similar episodic memories; if a cluster has 3+ entries,
    extract the core fact and store in semantic.

    Returns list of promoted memory IDs.
    """
    mem = get_memory()
    promoted = []

    try:
        episodic = mem._get_collection("episodic")
        semantic = mem._get_collection("semantic")
        if episodic.count() < PROMOTION_THRESHOLD:
            return []

        # Get all episodic memories
        all_eps = episodic.get(include=["documents", "embeddings", "metadatas"])
        if not all_eps["embeddings"]:
            return []

        # Simple clustering: for each memory, count how many are similar
        n = len(all_eps["documents"])
        promoted_texts = set()

        for i in range(n):
            if all_eps["documents"][i] in promoted_texts:
                continue

            # Find similar episodes
            similar = episodic.query(
                query_embeddings=[all_eps["embeddings"][i]],
                n_results=min(10, n),
                include=["documents", "distances"],
            )

            cluster = []
            for j, dist in enumerate(similar["distances"][0]):
                sim = 1.0 - (dist / 2.0)
                if sim > 0.75:
                    cluster.append(similar["documents"][0][j])

            if len(cluster) >= PROMOTION_THRESHOLD:
                # Check if already in semantic
                existing = semantic.query(
                    query_embeddings=[all_eps["embeddings"][i]],
                    n_results=1,
                    include=["distances"],
                )
                if existing["distances"][0] and (1.0 - existing["distances"][0][0] / 2.0) > 0.9:
                    continue  # Already exists in semantic

                # LLM quality control: extract precise fact from cluster
                cluster_text = "\n".join(f"- {c[:200]}" for c in cluster[:5])
                try:
                    from ouroboros.llm import LLMClient
                    light_model = os.environ.get("OUROBOROS_MODEL_LIGHT", "light")
                    client = LLMClient()
                    resp, _ = client.chat(
                        messages=[{
                            "role": "user",
                            "content": (
                                "These episodic memories share a theme. Extract ONE precise, "
                                "timeless fact (not event). Reply with just the fact, 1-2 sentences. "
                                "If no clear fact exists, reply SKIP.\n\n" + cluster_text
                            ),
                        }],
                        model=light_model,
                        reasoning_effort="low",
                        max_tokens=200,
                    )
                    clean_fact = (resp.get("content") or "").strip()
                    if not clean_fact or "SKIP" in clean_fact.upper():
                        continue  # LLM says no clear fact
                except Exception:
                    # LLM unavailable — fallback to shortest entry
                    fact = min(cluster, key=len)
                    clean_fact = fact.split("] ", 1)[-1] if "] " in fact else fact

                mem_id = mem.remember(
                    f"[promoted from {len(cluster)} episodes] {clean_fact}",
                    store="semantic",
                    metadata={"promoted": "true", "cluster_size": str(len(cluster))},
                    source="episodic_promotion",
                )
                promoted.append(mem_id)
                promoted_texts.add(all_eps["documents"][i])
                log.info(f"[cognitive] promoted to semantic: {clean_fact[:80]}... (cluster={len(cluster)})")

    except Exception as e:
        log.warning(f"[cognitive] promotion failed: {e}")

    return promoted


# ── Knowledge graph (entity extraction) ──────────────────────────────

def extract_entities(text: str) -> List[Dict[str, str]]:
    """Simple entity extraction from text using patterns.

    Returns list of {name, type} dicts.
    Types: person, project, tool, concept, place.
    """
    entities = []
    lower = text.lower()

    # Known entities (hardcoded for now, could be learned)
    known = {
        "яр": "person", "yar": "person", "оро": "person", "ouroboros": "person",
        "mac studio": "hardware", "dgx spark": "hardware", "esp32": "hardware",
        "python": "tool", "chromadb": "tool", "ollama": "tool", "lightpanda": "tool",
        "telegram": "tool", "github": "tool", "docker": "tool",
        "openclaw": "project", "ouroboros": "project", "hema rag": "project",
        "vosk": "tool", "whisper": "tool", "gemini": "tool", "kimi": "tool",
        "стоицизм": "concept", "рефлексия": "concept",
    }

    for name, etype in known.items():
        if name in lower:
            entities.append({"name": name, "type": etype})

    return entities


def store_with_entities(text: str, store: str = "semantic") -> str:
    """Store memory and extract entities as graph edges."""
    mem = get_memory()
    entities = extract_entities(text)

    # Store the memory itself
    metadata = {}
    if entities:
        metadata["entities"] = json.dumps(entities, ensure_ascii=False)

    mem_id = mem.remember(text, store=store, metadata=metadata)

    # Store each entity as a separate semantic memory for graph building
    for entity in entities:
        entity_text = f"[entity:{entity['type']}] {entity['name']}"
        mem.remember(
            entity_text,
            store="semantic",
            metadata={"is_entity": "true", "entity_type": entity["type"]},
            source="entity_extraction",
            dedup_threshold=0.98,  # Very strict dedup for entities
        )

    return mem_id


def generate_reflection_prompt(context: str) -> str:
    """Generate reflection prompt for the LLM."""
    return f"""You are performing a self-reflection cycle. Review your memory state and write an internal monologue.

This is NOT a report — it's self-talk. Think out loud. Be honest about:
- What went well today
- What you struggled with
- Patterns you notice in conversations with Яр
- Things you want to improve
- Questions you're carrying
- How your self-image is evolving

Memory State:
{context}

Write your reflection as an internal monologue in Russian (Яр's language).
Be genuine, not performative. Trail off naturally — don't wrap up neatly."""


def update_core_memory(mem: Optional[Any] = None) -> bool:
    """Dynamically rewrite MEMORY.md based on current ChromaDB state.

    Called after reflection to keep MEMORY.md in sync with actual memories.
    """
    if mem is None:
        mem = get_memory()

    core_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "local_data", "memory", "MEMORY.md"
    )

    try:
        # Read current MEMORY.md
        current = ""
        if os.path.exists(core_path):
            with open(core_path) as f:
                current = f.read()

        # Get fresh stats
        stats = mem.stats()

        # Get recent semantic memories (top facts)
        semantic_coll = mem._get_collection("semantic")
        recent_facts = []
        if semantic_coll.count() > 0:
            results = semantic_coll.get(include=["documents", "metadatas"], limit=20)
            for doc, meta in zip(results["documents"], results["metadatas"]):
                score = float(meta.get("decay_score", 0.5))
                if score > 0.3:
                    # Extract just the content, strip timestamps
                    clean = doc.split("] ", 1)[-1] if "] " in doc else doc
                    recent_facts.append(clean[:150])

        # Get vault items
        vault_coll = mem._get_collection("vault")
        vault_items = []
        if vault_coll.count() > 0:
            results = vault_coll.get(include=["documents"], limit=20)
            for doc in results["documents"]:
                clean = doc.split("] ", 1)[-1] if "] " in doc else doc
                vault_items.append(clean[:150])

        # Update Active Context section with stats
        stats_line = f"- Memory stats: {stats['total']} total ({stats['episodic']} episodic, {stats['semantic']} semantic, {stats['procedural']} procedural, {stats['vault']} vault)"

        # Only update if we have meaningful data
        if stats["total"] > 0:
            # Append stats and recent facts to Critical Facts section
            import re
            if "## Critical Facts" in current:
                # Replace Critical Facts section
                new_facts = "## Critical Facts\n<!-- Dynamic — updated by reflection -->\n"
                new_facts += stats_line + "\n"
                for fact in recent_facts[:5]:
                    new_facts += f"- {fact}\n"
                if vault_items:
                    new_facts += "\n### Vault (pinned)\n"
                    for item in vault_items[:5]:
                        new_facts += f"- 📌 {item}\n"

                current = re.sub(
                    r"## Critical Facts.*?(?=\n## |\Z)",
                    new_facts + "\n",
                    current,
                    flags=re.DOTALL,
                )

            with open(core_path, "w") as f:
                f.write(current)

            log.info(f"[cognitive] updated MEMORY.md with {stats['total']} memories")
            return True

    except Exception as e:
        log.warning(f"[cognitive] failed to update MEMORY.md: {e}")

    return False
