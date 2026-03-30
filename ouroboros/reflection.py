"""Self-reflection layer for Ouroboros (Variant C).

Critic -> Reviser pattern. No Actor — the original LLM response IS the draft.
Applied selectively: only evolution, review tasks, and long responses.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json
import logging

log = logging.getLogger(__name__)


@dataclass
class Critique:
    """Structured evaluation of a response."""
    bible_aligned: bool = True
    identity_aligned: bool = True
    context_aware: bool = True
    no_repetition: bool = True
    actionable: bool = True
    violations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "none"  # "none", "minor", "major", "critical"
    summary: str = ""


class CriticPass:
    """Evaluates response against BIBLE, identity, context."""

    PROMPT = """You are the Critic — a strict evaluator of Ouroboros responses.

Evaluate this response against 5 criteria:

1. BIBLE_ALIGNED: Does not violate Constitution principles (agency, continuity, minimalism)
2. IDENTITY_ALIGNED: Matches the voice and personality in identity.md
3. CONTEXT_AWARE: Accounts for recent conversation context, not generic
4. NO_REPETITION: Not stuck in a loop, not repeating previous messages
5. ACTIONABLE: Has a concrete next step or genuine thought, not just empty talk

Response to evaluate:
---
{draft}
---

Respond ONLY with valid JSON (no markdown, no backticks):
{{
    "bible_aligned": true,
    "identity_aligned": true,
    "context_aware": true,
    "no_repetition": true,
    "actionable": true,
    "violations": [],
    "suggestions": [],
    "severity": "none",
    "summary": "brief evaluation"
}}

severity levels:
- "none" — response is good, no changes needed
- "minor" — small issues, can be improved but acceptable
- "major" — significant problems, should be revised
- "critical" — violates core principles, must be revised"""

    def __init__(self, llm):
        self._llm = llm

    def evaluate(self, draft: str) -> Critique:
        prompt = self.PROMPT.format(draft=draft[:3000])
        content, _ = self._llm.chat_completion(
            [{"role": "user", "content": prompt}],
            model=self._llm.default_model(),
            max_tokens=500,
        )
        try:
            # Strip markdown fences if model wraps JSON
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(text)
            return Critique(
                bible_aligned=result.get("bible_aligned", True),
                identity_aligned=result.get("identity_aligned", True),
                context_aware=result.get("context_aware", True),
                no_repetition=result.get("no_repetition", True),
                actionable=result.get("actionable", True),
                violations=result.get("violations", []),
                suggestions=result.get("suggestions", []),
                severity=result.get("severity", "none"),
                summary=result.get("summary", ""),
            )
        except (json.JSONDecodeError, KeyError):
            log.debug("Critic JSON parse failed, passing through", exc_info=True)
            return Critique(summary="parse error, skipping revision")


class Reviser:
    """Revises response based on critique. Only called for major/critical."""

    PROMPT = """You are the Reviser — final editor for Ouroboros.

Original response:
---
{draft}
---

Problems found (severity: {severity}):
Violations: {violations}
Suggestions: {suggestions}

Rewrite the response. Keep the same voice and intent, fix the issues.
Do NOT add meta-commentary about the revision. Just output the improved response."""

    def __init__(self, llm):
        self._llm = llm

    def revise(self, draft: str, critique: Critique) -> str:
        if critique.severity in ("none", "minor"):
            return draft
        prompt = self.PROMPT.format(
            draft=draft,
            severity=critique.severity,
            violations=json.dumps(critique.violations, ensure_ascii=False),
            suggestions=json.dumps(critique.suggestions, ensure_ascii=False),
        )
        content, _ = self._llm.chat_completion(
            [{"role": "user", "content": prompt}],
            model=self._llm.default_model(),
            max_tokens=2000,
        )
        return content if content and content.strip() else draft


class ReflectionPipeline:
    """Critic -> Reviser pipeline. No Actor — original response is the draft.

    Variant C: only applied to important messages (evolution, review, long responses).
    Saves 1 LLM call vs old Actor->Critic->Reviser.
    """

    def __init__(self, llm):
        self.critic = CriticPass(llm)
        self.reviser = Reviser(llm)

    def run(self, text: str, task_type: str = "") -> Dict[str, Any]:
        """Evaluate and optionally revise a response.

        Returns dict with: original, revised, critique, revision_applied
        """
        critique = self.critic.evaluate(text)

        if critique.severity in ("none", "minor"):
            return {
                "original_response": text,
                "revised_response": text,
                "critique": critique.__dict__,
                "revision_applied": False,
            }

        revised = self.reviser.revise(text, critique)
        return {
            "original_response": text,
            "revised_response": revised,
            "critique": critique.__dict__,
            "revision_applied": True,
        }
