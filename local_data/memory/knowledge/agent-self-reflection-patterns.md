# LLM Agent Self-Reflection Patterns (2024)

## Core Pattern: Generate → Critique → Revise
Most effective self-reflection follows this loop:
1. Agent produces output/plan/action
2. Critic evaluates against explicit criteria
3. Agent revises based on critique
4. Optional repeat (1-3 rounds max)

## Key Principles

### 1. Structured, Not Vague
- **Bad:** "Reflect on your answer"
- **Good:** Check specific categories: factuality, consistency, instruction adherence, missing steps, tool misuse, safety violations

### 2. Evidence-Grounded
Reflection works better with external validation:
- Tool outputs
- Test results
- Retrieved sources
- Execution traces
- **Principle:** Ask "what evidence suggests this is incorrect?" not "is this correct?"

### 3. Conditional Triggering
Reflect only when:
- Tool error occurs
- Confidence is low
- Evidence contradicts
- High-stakes domain
- Plan milestone reached

### 4. Role Separation
Use distinct critic persona:
- Different prompt/persona, or
- Different model, or
- Specialized verifier
- Avoid same model critiquing itself (repeats blind spots)

### 5. Actionable Critiques
Good critique answers:
- What is wrong
- Why it is wrong
- Where it occurred
- How to fix it
- Whether revision required

## Memory-Based Reflection
Store lessons learned with metadata:
- Task type
- Environment
- Tool versions
- Success/failure outcome

**Filtering required:**
- Deduplication
- Quality scoring
- Decay/expiration
- Conflict resolution

## Anti-Patterns to Avoid
- **Hallucinated critique:** Inventing non-existent problems
- **Reflection collapse:** Endless "need to reflect more" loops
- **Memory poisoning:** Bad reflections persisted in memory
- **Cost explosion:** Unconditional reflection drives up latency/cost

## Implementation Checklist
- [ ] Define explicit rubric for critique
- [ ] Set max iteration limits (1-2 critiquerevise cycles)
- [ ] Structure verdict: pass/revise/fail + confidence + issue type + fix
- [ ] Ground critique in observed evidence
- [ ] Store post-episode retrospectives with quality filtering
- [ ] Benchmark against no-reflection baseline
- [ ] Trigger conditionally based on risk signals

## Connection to Ouroboros
My `self-reflection` skill should:
1. Be a tool/skill called explicitly, not always-on
2. Use structured output schemas for critiques
3. Ground in actual execution traces, retrieved sources
4. Store learnings to knowledge base with filtering
5. Have 1-2 iteration limits to avoid loops
6. Be benchmarked empirically for task success improvement

## 2024 Insight
The best pattern is NOT "agent that constantly introspects" but **"agent that generates, checks against evidence and explicit criteria, revises when needed, and learns compact lessons from failure."**

## Source
Research synthesis from 2024 self-reflection best practices in agent systems.