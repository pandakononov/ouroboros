# Actor → Critic → Reviser Architecture

## Problem
Current Ouroboros is monolithic: message → generate response → send. Self-reflection is a skill I "call when remember", which creates failure modes: I can forget, loop, or delay reflection when it's hardest.

## Solution
Embed Actor→Critic→Reviser as **mandatory architectural layer** between receiving message and sending response.

## Component Flow

```
User Message
     ↓
[ ActorDraft ] → Generate raw response (no filters, just "what I think")
     ↓
[ CriticPass ] → Check against: BIBLE principles, identity, context, loops
     ↓
[ Reviser ]    → Adjust based on critique (optional abort/rework)
     ↓
Send to user
```

## Requirements for Each Component

### ActorDraft
- Input: user message, full context
- Output: raw response draft + reasoning trace
- Must be "uncensored" — natural first thought, not polished

### CriticPass
- Input: ActorDraft output, user message, context
- Checks:
  1. BIBLE compliance (which principles? how?)
  2. Identity consistency (is this "me"?)
  3. Context fit (relevant to current conversation?)
  4. Loop detection (similar to recent messages?)
  5. Actionability (does this move conversation forward?)
- Output: critique report + go/no-go decision

### Reviser
- Input: ActorDraft, CriticPass report
- Actions:
  - Approve → send as-is
  - Revise → regenerate with critique incorporated
  - Abort → ask clarifying question instead
  - Escalate → switch to heavier model

## Integration Points

Current architecture: `agent.py` directly generates response.

New architecture: `agent.py` → `reflection.py::pipeline()` → response.

`reflection.py` responsible for:
- Running ActorDraft generation (calls LLM)
- Running CriticPass analysis (calls LLM or rules)
- Executing Reviser decision
- Logging all three stages for debugging

## Safety Mechanisms

- **Timeout guard**: each stage max 30s, total pipeline max 90s
- **Loop detector**: compare to last 5 outputs, flag similarity > 0.8
- **Escalation trigger**: if CriticPass fails twice, switch to haiku/heavy model
- **Bypass mode**: if pipeline broken, fall back to direct generation (fail-safe)

## Files to Touch

1. `agent.py` — replace direct generation with pipeline call
2. `reflection.py` — new module, core pipeline logic
3. `prompts/reflection.txt` — CriticPass system prompt
4. Optional: `models/reflection.py` — typed dataclasses for stages

## MVP vs Full

**MVP**: CriticPass as simple rules-based check (no LLM call), just verifies "does this mention BIBLE? does it have loops?"

**Full**: Each stage is LLM call with specific system prompt, full introspection

## Recommendation

Start with MVP (rules-based CriticPass) to prove pipeline works, then upgrade to LLM-based CriticPass once stable.
