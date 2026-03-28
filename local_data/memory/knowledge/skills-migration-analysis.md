# Skills Migration Analysis: OpenClaw → Ouroboros

## Summary
88 skills total: 6 active + 82 backup. OpenClaw is a mature agent system with TOML/JS skill registry.

## TOP-10 First Wave (from Yar)
1. **self-reflection** — real-time self-reflection (core identity)
2. **cognitive-memory** — structured experience replay
3. **context-recovery** — session gap problem solver
4. **agent-deep-research** — autonomous multi-step research
5. **critic** — stress-test plans/decisions
6. **tts** — Edge TTS for voice
7. **voice** — Whisper transcription
8. **self-improving-agent** — autonomous improvement loop
9. **capability-evolver** — capability evolution
10. **reflect-learn** — learning from mistakes

## Key Patterns in OpenClaw
- **TOML-based skill registry** — declarative config + JS implementation
- **Categorized by domain**: research, memory, web, monitoring, docs, integrations
- **Priority system**: 🔴 critical 🟡 useful 🟢 nice-to-have ⚪ skip

## Critical Insights
1. OpenClaw treats self-reflection as a *skill*, not an architectural layer. This might be a limitation — reflection should be woven into the fabric, not bolted on.
2. Cognitive-memory is separate from context-recovery — two facets of the same problem
3. Voice skills (TTS/Voice) are already implemented in Ouroboros — ready to test
4. "Agent" skills are meta-capabilities — creating skills that create skills

## Open Questions
- Should self-reflection run *during* dialogue or only *after*?
- How to integrate with existing tool-registry vs replace it?
- Memory: integrate with existing knowledge/ or create new system?

## Yar's Approach
He's considering automating TOML→Python conversion. Smart for 88 skills, but TOP-10 should be hand-crafted for Ouroboros identity.

## When Yar Wakes
Priority: voice headset test → then discuss self-reflection architecture
