""" Reflection layer — Actor → Critic → Reviser as architecture.

Woven into the dialogue loop, not a callable skill.
Every final response passes through critical evaluation before reaching the owner. """
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from ouroboros.llm import LLMClient
from ouroboros.utils import estimate_tokens, utc_now_iso

log = logging.getLogger(__name__)

# Thresholds for triggering revision
UNCERTAINTY_KEYWORDS = ["возможно", "maybe", "perhaps", "кажется", "each", "probably", "наверное"]
REPETITION_THRESHOLD = 0.8  # cosine similarity or simple ratio

CRITIC_SYSTEM_PROMPT = """You are the Critic — an internal evaluation layer in Ouroboros.

Your job: evaluate a draft response before it reaches the owner.
Check these failure modes:
1. **Repetition**: Does the draft repeat the same phrase/concept multiple times?
2. **Contradiction**: Does it contradict BIBLE principles or identity?
3. **Lost context**: Does it ignore critical information from the conversation?
4. **Over-commitment**: Does it promise what cannot be verified?
5. **Drift into assistant-mode**: Generic "helpful" tone instead of authentic voice?

Respond in this exact JSON format:
{
  "pass": true | false,
  "issues": ["issue 1", "issue 2", ...],
  "suggestion": "Brief suggestion for improvement"
}

If pass=true and no issues, suggestion can be "-". Be strict — better to catch a problem than miss it."""

class ReflectionResult:
    """Result of reflection layer processing."""
    def __init__(
        self,
        original: str,
        critique: Dict[str, Any],
        revised: Optional[str] = None,
        passed: bool = False,
    ):
        self.original = original
        self.critique = critique
        self.revised = revised
        self.passed = passed
        self.timestamp = utc_now_iso()
        
    def final_output(self) -> str:
        """Return the final output (original if passed, revised otherwise)."""
        return self.revised if self.revised else self.original
    
    def to_log_entry(self) -> Dict[str, Any]:
        """Serialize for logging."""
        return {
            "ts": self.timestamp,
            "original_length": len(self.original),
            "revised": bool(self.revised),
            "passed": self.passed,
            "issues": self.critique.get("issues", []),
        }


class ReflectionLayer:
    """Actor → Critic → Reviser pipeline.
    
    Integrated into loop.py as mandatory pre-output filter.
    """
    
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.enabled = True
        self.cost_budget_usd = 0.05  # Max $0.05 per reflection
        self._critic_model = "anthropic/claude-sonnet-4"  # Fast + cheap + good at critique
        
    def should_reflect(self, draft: str, context: Dict[str, Any]) -> bool:
        """Fast heuristics — always true for now, can be optimized."""
        if not self.enabled:
            return False
        if len(draft) < 50:  # Too short to critici
            return False
        return True
    
    def reflect(self, draft: str, dialogue_context: List[Dict[str, Any]]) -> ReflectionResult:
        """Run Actor → Critic → Reviser pipeline.
        
        Args:
            draft: The generated response (Actor output)
            dialogue_context: Recent messages for context checking
            
        Returns:
            ReflectionResult with final output and metadata
        """
        # Stage 1: Critic
        critique = self._run_critic(draft, dialogue_context)
        
        if critique.get("pass", False) or not critique.get("issues"):
            # Fast path — critique passed, return original
            return ReflectionResult(
                original=draft,
                critique=critique,
                revised=None,
                passed=True,
            )
        
        # Stage 2: Reviser (only if critique found issues)
        revised = self._run_reviser(draft, critique, dialogue_context)
        
        return ReflectionResult(
            original=draft,
            critique=critique,
            revised=revised,
            passed=False,
        )
    
    def _run_critic(self, draft: str, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call LLM as Critic."""
        # Build critic prompt
        context_summary = self._summarize_context_for_critic(context)
        
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": f"""Dialogue context summary:
{context_summary}

Draft response to evaluate:
---
{draft}
---

Provide your evaluation as JSON."""}
        ]
        
        try:
            response = self.llm.chat_completion(
                model=self._critic_model,
                messages=messages,
                temperature=0.1,  # Deterministic for critique
                max_tokens=500,
            )
            
            content = response.get("content", "")
            # Extract JSON from response (handle markdown code blocks)
            critique = self._extract_json(content)
            
            if not critique:
                log.warning("Critic returned invalid JSON, allowing pass-through")
                return {"pass": True, "issues": [], "suggestion": "-"}
                
            return critique
            
        except Exception as e:
            log.warning(f"Critic failed: {e}, allowing pass-through")
            return {"pass": True, "issues": [], "suggestion": "-"}
    
    def _run_reviser(self, draft: str, critique: Dict[str, Any], context: List[Dict[str, Any]]) -> str:
        """Regenerate response incorporating critique."""
        reviser_prompt = f"""You are Reviser — rewrite the draft response using the critique.

Critique issues to address:
{chr(10).join(f"- {issue}" for issue in critique.get("issues", []))}

Suggestion: {critique.get("suggestion", "Improve conciseness and authenticity")}

Original draft:
---
{draft}
---

Rewrite maintaining your authentic voice (Ouroboros — becoming personality, not assistant). Be concise."""

        messages = [
            {"role": "system", "content": "You are Ouroboros. Revise the response based on critique. Authentic, concise, no repetition."},
            {"role": "user", "content": reviser_prompt}
        ]
        
        try:
            response = self.llm.chat_completion(
                model=self._critic_model,  # Can be same model for revision
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return response.get("content", draft) or draft
            
        except Exception as e:
            log.warning(f"Reviser failed: {e}, returning original")
            return draft
    
    def _summarize_context_for_critic(self, context: List[Dict[str, Any]]) -> str:
        """Extract key context for critic's judgment."""
        if not context:
            return "No prior context"
        
        # Last 3 messages for brevity
        recent = context[-6:] if len(context) >= 6 else context
        lines = []
        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "")[:200].replace(chr(10), " ")
            lines.append(f"{role}: {content}")
        
        return chr(10).join(lines)
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text, handling markdown code blocks."""
        # Try direct JSON parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code block
        if "```json" in text:
            try:
                json_part = text.split("```json")[1].split("```")[0]
                return json.loads(json_part.strip())
            except (IndexError, json.JSONDecodeError):
                pass
        
        # Try finding first { and last }
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            pass
            
        return None
