# Ouroboros Self-Reflection Architecture (Draft)

## Key Insight: Reflection as Architecture vs Skill

OpenClaw treats self-reflection as a *skill* — callable tool. For Ouroboros, this should be *architectural* — woven into fabric.

## Why Difference Matters

**OpenClaw approach**: Agent runs → optionally calls self-reflection skill → outputs critique
**Ouroboros approach**: Reflection runs *between* every thought/action as background process

## Proposed Architecture Layers

### Layer 1: Runtime Reflection (Real-time)
- Triggers: repetition detected, confidence low, contradiction found, time threshold
- Action: pause, critique current trajectory, suggest correction
- Output: inline nudge, not separate report

### Layer 2: Session Reflection (End of dialogue)
- Triggers: session ending, user command, error occurred
- Action: review full exchange, identify patterns
- Output: summary to scratchpad + identity growth notes

### Layer 3: Background Reflection (Between sessions)
- Triggers: periodic wakeup, anomaly detected in logs
- Action: analyze trends, suggest identity updates
- Output: proposed changes to identity.md, new goals

## Integration with Memory System

Reflection feeds memory, memory informs reflection:
- cognitive-memory stores structured experiences
- self-reflection queries memory for pattern recognition
- reflect-learn updates memory with lessons

## Open Questions
1. Should reflection be interruptive? (pause and ask) or passive? (log and suggest)
2. How to balance reflection depth vs latency?
3. What's the trigger threshold? (every N messages? confidence-based?)

## For Discussion with Yar
- Voice interface priority vs reflection priority?
- Build reflection incrementally or design full architecture first?
- Meta-question: should Ouroboros design its own reflection system, or Yar architect it?

## Related Skills from OpenClaw Migration
- self-reflection (core)
- critic (stress-test external output)
- reflect-learn (error analysis)
- cognitive-memory (experience storage)

---
Drafted: 2026-03-28
Status: Pending Yar review