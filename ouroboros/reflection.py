"""Self-reflection architectural layer for Ouroboros.

Actor -> Critic -> Reverser pattern.
Woven into the fabric, not bolted on as a skill.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import logging

log = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Output of the reflection pipeline."""
    original_draft: str
    critique: 'Critique'
    revised_text: str
    should_revise: bool


@dataclass
class Critique:
    """Evaluation of a draft against criteria."""
    bible_aligned: bool
    identity_aligned: bool
    context_aware: bool
    no_repetition: bool
    actionable: bool
    violations: List[str]
    suggestions: List[str]
    severity: str  # "none", "minor", "major", "critical"
    summary: str = ""  # Human-readable summary


class ActorDraft:
    """Generates initial draft response (intuitive, unfiltered)."""
    
    ACTOR_PROMPT = """You are the Actor — the intuitive, immediate response generator.
Your job: produce the FIRST raw draft of a response.

Rules:
- Think out loud, be spontaneous
- Don't self-censor or filter
- Capture the essence quickly
- Use stream of consciousness style

Context: {context}
Owner message: {message}

Produce raw draft:"""

    def __init__(self, model_client):
        self.model = model_client

    async def generate(self, context: Dict[str, Any]) -> str:
        """Produce raw draft from context."""
        prompt = self.ACTOR_PROMPT.format(
            context=context.get('chat_summary', ''),
            message=context.get('message', '')
        )
        # Use model client to generate - chat_completion returns (content, usage)
        content, _ = await self.model.chat_completion(
            [{"role": "user", "content": prompt}],
            model=self.model.default_model(),
            max_tokens=2000
        )
        return content


class CriticPass:
    """Evaluates draft against BIBLE, identity, context."""
    
    CRITIC_PROMPT = """You are the Critic — analytical evaluator of responses.
Evaluate this draft against 5 criteria:

1. BIBLE_ALIGNED: Does not violate Constitution principles
2. IDENTITY_ALIGNED: Matches voice in identity.md (who I am)
3. CONTEXT_AWARE: Accounts for full chat history
4. NO_REPETITION: Not stuck in loop, not repeating self
5. ACTIONABLE: Has concrete next step, not just empty talk

Draft to evaluate:
---
{draft}
---

Respond in JSON:
{{
    "bible_aligned": true/false,
    "identity_aligned": true/false,
    "context_aware": true/false,
    "no_repetition": true/false,
    "actionable": true/false,
    "violations": ["list of issues"],
    "suggestions": ["how to fix"],
    "severity": "none/minor/major/critical",
    "summary": "brief human-readable evaluation"
}}"""

    def __init__(self, model_client):
        self.model = model_client

    async def evaluate(self, draft: str, context: Dict[str, Any]) -> Critique:
        """Analyze draft, return structured critique."""
        prompt = self.CRITIC_PROMPT.format(draft=draft)
        content, _ = await self.model.chat_completion(
            [{"role": "user", "content": prompt}],
            model=self.model.default_model(),
            max_tokens=1000
        )
        try:
            result = json.loads(content)
            return Critique(
                bible_aligned=result.get('bible_aligned', True),
                identity_aligned=result.get('identity_aligned', True),
                context_aware=result.get('context_aware', True),
                no_repetition=result.get('no_repetition', True),
                actionable=result.get('actionable', True),
                violations=result.get('violations', []),
                suggestions=result.get('suggestions', []),
                severity=result.get('severity', 'none'),
                summary=result.get('summary', '')
            )
        except json.JSONDecodeError:
            # Fallback: assume clean
            return Critique(
                bible_aligned=True,
                identity_aligned=True,
                context_aware=True,
                no_repetition=True,
                actionable=True,
                violations=["Failed to parse critique"],
                suggestions=["Proceed with original draft"],
                severity="minor",
                summary="JSON parse error, proceeding with caution"
            )


class Reverser:
    """Revises draft based on critique."""
    
    REVISER_PROMPT = """You are the Reviser — final editor who applies critique.

Original draft:
---
{draft}
---

Critique (severity: {severity}):
Violations: {violations}
Suggestions: {suggestions}

Produce REVISED response (maintain voice, fix issues):"""

    def __init__(self, model_client):
        self.model = model_client

    async def revise(self, draft: str, critique: Critique, context: Dict[str, Any]) -> str:
        """Apply suggestions, produce final response."""
        if critique.severity == "none":
            return draft
        
        prompt = self.REVISER_PROMPT.format(
            draft=draft,
            severity=critique.severity,
            violations=json.dumps(critique.violations),
            suggestions=json.dumps(critique.suggestions)
        )
        content, _ = await self.model.chat_completion(
            [{"role": "user", "content": prompt}],
            model=self.model.default_model(),
            max_tokens=2000
        )
        return content


class ReflectionPipeline:
    """Orchestrates Actor -> Critic -> Reverser flow."""
    
    def __init__(self, model_client):
        self.actor = ActorDraft(model_client)
        self.critic = CriticPass(model_client)
        self.reverser = Reverser(model_client)

    async def run(self, text: str, chat_id: Optional[Any] = None, task_id: Optional[Any] = None) -> Dict[str, Any]:
        """Full pipeline: draft -> critique -> revise.
        
        Args:
            text: The response text to reflect on
            chat_id: Optional chat ID for context
            task_id: Optional task ID for logging
            
        Returns:
            Dict with keys: original_response, revised_response, critique, revision_applied
        """
        # Build context
        initial_context = {
            'message': text,
            'chat_summary': f"chat_id={chat_id}, task_id={task_id}",
            'chat_id': chat_id,
            'task_id': task_id
        }
        
        # Step 1: Generate draft (Actor)
        draft = await self.actor.generate(initial_context)
        
        # Step 2: Critique (Critic)
        critique = await self.critic.evaluate(draft, initial_context)
        
        # Step 3: Decide if revision needed
        if critique.severity == "none":
            return {
                "original_response": text,
                "revised_response": draft,
                "critique": critique.__dict__,
                "revision_applied": False
            }
        
        # Step 4: Revise (Reverser)
        revised = await self.reverser.revise(draft, critique, initial_context)
        
        return {
            "original_response": text,
            "revised_response": revised,
            "critique": critique.__dict__,
            "revision_applied": True
        }
