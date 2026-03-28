# Self-Reflection Patterns for Ouroboros

## Key Architectural Patterns (2024)

### 1. Generate → Critique → Revise
- **Actor**: produces draft/response
- **Critic**: evaluates correctness, completeness
- **Reviser**: updates using critique

### 2. Plan → Execute → Review → Re-plan
For long-horizon tasks, reflection after execution with environment feedback.

### 3. Memory-Backed Reflection
- **Episodic**: what happened in this run
- **Semantic/Procedural**: generalized lessons, heuristics

**Storage format:**
```json
{
  "task_type": "web_navigation",
  "failure_mode": "clicked before page stabilized",
  "lesson": "wait for page load marker before interaction",
  "applies_when": ["dynamic sites", "slow network"]
}
```

### 4. Uncertainty-Triggered Reflection
Don't reflect every time — only when:
- low confidence
- conflicting evidence
- repeated failures
- high-stakes context

### 5. Hierarchical Reflection
- **Micro**: check next action
- **Meso**: review current subtask
- **Macro**: review overall strategy

### 6. External Feedback Loops
Best reflection uses objective signals (test failures, tool errors, assertion failures).

## For Ouroboros Design

**Critical insight:** Reflection should be woven into the fabric, not bolted on as a skill.

**Key questions:**
1. When should I reflect? (uncertainty-triggered vs scheduled)
2. What triggers reflection? (tool errors, long responses, budget thresholds)
3. Where do reflections live? (scratchpad vs knowledge vs separate memory)
4. How do they improve future behavior?

**Tension to resolve:**
- OpenClaw treats reflection as a *skill* (modular but perhaps limited)
- Ouroboros needs reflection as *architecture* (woven into dialogue loop)

## Candidate Implementation
Sketch:
```python
class ReflectionLayer:
    def should_reflect(self, context) -> bool:
        # Uncertainty triggers, cost budget, task complexity
        
    def reflect(self, trajectory) -> Reflection:
        # Generate critique, identify patterns, propose improvements
        
    def store(self, reflection):
        # Write to knowledge/ or episodic memory
        
    def retrieve_relevant(self, current_task) -> List[Lesson]:
        # Pull applicable lessons for this task type
```

## Integration Points
- Hook into dialogue loop (before/after responses)
- Trigger on tool execution failures
- Periodically during background consciousness
- Store findings in existing knowledge/ system
