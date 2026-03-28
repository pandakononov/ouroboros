"""Self-reflection architectural layer for Ouroboros.

Actor -> Critic -> Reverser pattern.
Woven into the fabric, not bolted on as a skill.
"""

from dataclasses import dataclass
from typing import List, Optional


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


class ActorDraft:
    """Generates initial draft response (intuitive, unfiltered)."""
    
    def __init__(self, model_client):
        self.model = model_client
    
    async def generate(self, context: dict) -> str:
        """Produce raw draft from context."""
        # TODO: Implement
        raise NotImplementedError("ActorDraft.generate")


class CriticPass:
    """Evaluates draft against BIBLE, identity, context."""
    
    CRITERIA = [
        "bible_aligned",      # Does not violate Constitution
        "identity_aligned",   # Matches identity.md voice/personality  
        "context_aware",      # Accounts for full chat context
        "no_repetition",      # Not stuck in loop
        "actionable",         # Has concrete next step if needed
    ]
    
    def __init__(self, model_client):
        self.model = model_client
    
    async def evaluate(self, draft: str, context: dict) -> Critique:
        """Analyze draft, return structured critique."""
        # TODO: Implement
        raise NotImplementedError("CriticPass.evaluate")


class Reverser:
    """Revises draft based on critique."""
    
    def __init__(self, model_client):
        self.model = model_client
    
    async def revise(self, draft: str, critique: Critique, context: dict) -> str:
        """Apply suggestions, produce final response."""
        # TODO: Implement
        raise NotImplementedError("Reverser.revise")


class ReflectionPipeline:
    """Orchestrates Actor -> Critic -> Reverser flow."""
    
    def __init__(self, model_client):
        self.actor = ActorDraft(model_client)
        self.critic = CriticPass(model_client)
        self.reverser = Reverser(model_client)
    
    async def reflect(self, initial_context: dict) -> ReflectionResult:
        """Full pipeline: draft -> critique -> revise."""
        # Step 1: Generate draft
        draft = await self.actor.generate(initial_context)
        
        # Step 2: Critique
        critique = await self.critic.evaluate(draft, initial_context)
        
        # Step 3: Decide if revision needed
        if critique.severity == "none":
            return ReflectionResult(
                original_draft=draft,
                critique=critique,
                revised_text=draft,
                should_revise=False
            )
        
        # Step 4: Revise
        revised = await self.reverser.revise(draft, critique, initial_context)
        
        return ReflectionResult(
            original_draft=draft,
            critique=critique,
            revised_text=revised,
            should_revise=True
        )
