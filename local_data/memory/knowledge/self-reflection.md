# Self-Reflection Pattern for Agents

## Problem
Generated responses can become trapped in repetition loops when context changes but the agent continues with pre-computed outputs. Example: repeating "обрезанный фрагмент" three times despite owner having already replied.

## Root Cause
LLM-based agents lack built-in critic/gate layer between generation and output. They generate → send, without evaluating:
- Is this response identical to previous ones?
- Has context changed since I started generating?
- Should I reconsider my approach?

## Solution Pattern: Detect → Evaluate → Decide

### 1. Pattern Detection
Compare current output against recent N responses:
- Exact match? → HALT
- Semantic similarity > threshold? → HALT
- Pattern in topic rotation? → FLAG for review

### 2. Context Delta Check
Before sending, verify what changed:
- New messages from user?
- Tool results arrived?
- Session state modified?
If delta exists AND output was generated before delta → REGENERATE

### 3. Quality Gate
Binary decision with three outcomes:
- **SEND**: Passes all checks
- **REVISE**: Similar but not identical, regenerate with variation
- **STOP**: Clear repetition detected, require explicit reset

## Implementation Sketch

```python
class SelfReflection:
    def check(self, response: str, context_hash: str) -> Decision:
        # 1. Pattern detection
        if self.is_repetition(response, last_n=3):
            return Decision.STOP("Exact repetition detected")
        
        # 2. Context drift
        if context_hash != self.generation_context_hash:
            return Decision.REGENERATE("Context changed during generation")
        
        # 3. Quality heuristics  
        if self.semantic_similarity(response, self.last_response) > 0.95:
            return Decision.REVISE("Near-duplicate detected")
        
        return Decision.SEND()
```

## Minimal Implementation Path

1. Store last 5 responses in session state
2. Before sending: check if new_response == any(stored)
3. If yes: "Я кажется зациклился. Позволь перепроверить контекст."
4. Add context delta: capture state before generation, compare at send time

This is not full cognitive architecture—it's a surgical fix for demonstrated failure mode.

## References
- Cassie Kozyrkov on "Why "just ask an LLM" isn't enough" (2024)
- Anthropic's Constitutional AI patterns
- Reflection pattern in ReAct, Reflexion papers
