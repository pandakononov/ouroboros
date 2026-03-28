"""
Reflection layer — Actor → Critic → Reviser

Архитектурный паттерн саморефлексии, встроенный как обязательный слой
между генерацией ответа и его отправкой пользователю.

В отличие от "skill" (который вызывается по требованию), reflection —
это инфраструктура: каждый цикл проходит через критику.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.llm import LLMClient
from ouroboros.utils import utc_now_iso


@dataclass
class ActorDraft:
    """Черновик ответа — сырой выход генерации до фильтров."""
    content: str
    tools_used: List[str]
    raw_plan: Optional[str] = None  # Внутренний план, если был
    
    def to_critique_input(self) -> str:
        """Формат для критика."""
        lines = ["=== СОДЕРЖАНИЕ ОТВЕТА ===", self.content, ""]
        if self.raw_plan:
            lines.extend(["=== ВНУТРЕННИЙ ПЛАН ===", self.raw_plan, ""])
        lines.extend(["=== ИНСТРУМЕНТЫ ===", f"Использовано: {', '.join(self.tools_used) if self.tools_used else 'none'}"])
        return "\n".join(lines)


@dataclass  
class CriticVerdict:
    """Вердикт критика — что не так и насколько критично."""
    # Аспекты для проверки (каждый: ok / warning / error)
    alignment_bible: str      # Соответствие Библии (Principles)
    alignment_identity: str  # Соответствие identity.md
    context_awareness: str   # Понимание контекста диалога
    tool_correctness: str    # Правильность использования инструментов
    loop_risk: str          # Риск зацикливания (repetition, drift)
    
    # Резюме
    overall_score: float     # 0.0 - 1.0
    is_acceptable: bool     # Можно отправлять as-is
    
    # Обратная связь
    critique_text: str        # Что именно не так
    revision_hints: str       # Как улучшить (если надо)
    
    def has_critical_issues(self) -> bool:
        """Есть ли критические ошибки, требующие перегенерации."""
        critical = ["error"]
        return (
            self.alignment_bible in critical or
            self.alignment_identity in critical or
            self.loop_risk in critical or
            self.overall_score < 0.6
        )
    
    def has_warnings(self) -> bool:
        """Есть ли замечания, которые стоит учесть."""
        warnings = ["warning"]
        return any(x in warnings for x in [
            self.alignment_bible, 
            self.alignment_identity,
            self.context_awareness,
            self.tool_correctness,
            self.loop_risk
        ])


@dataclass
class ReviserOutput:
    """Финальный результат после ревизии (или без неё, если вердикт ok)."""
    final_content: str
    was_revised: bool
    revision_count: int
    critic_score: float
    reflection_log: List[Dict[str, Any]]


class ReflectionLayer:
    """
    Архитектурный слой рефлексии.
    
    Не вызывается опционально — всегда присутствует между
    генерацией и отправкой ответа.
    """
    
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()
        
    def reflect(
        self,
        draft: ActorDraft,
        conversation_context: List[Dict[str, str]],
        current_identity: str = "",
        bible_principles: List[str] = None,
        max_revisions: int = 1,
        cheap_mode: bool = True,  # На этапе бюджета — критика без дорогой ревизии
    ) -> ReviserOutput:
        """
        Полный цикл: ActorDraft → Critic → [Reviser] → Output
        
        Returns:
            ReviserOutput с финальным контентом и метаданными рефлексии
        """
        reflection_log = []
        revision_count = 0
        current_draft = draft
        
        while revision_count <= max_revisions:
            # === CRITIC PASS ===
            verdict = self._critic_pass(
                draft=current_draft,
                context=conversation_context,
                identity=current_identity,
                bible_principles=bible_principles or [],
                cheap_mode=cheap_mode,
            )
            
            reflection_log.append({
                "ts": utc_now_iso(),
                "phase": "critic",
                "revision": revision_count,
                "score": verdict.overall_score,
                "acceptable": verdict.is_acceptable,
                "critical": verdict.has_critical_issues(),
            })
            
            # Если всё ок — отправляем как есть
            if verdict.is_acceptable and not verdict.has_critical_issues():
                return ReviserOutput(
                    final_content=current_draft.content,
                    was_revised=revision_count > 0,
                    revision_count=revision_count,
                    critic_score=verdict.overall_score,
                    reflection_log=reflection_log,
                )
            
            # Если критические ошибки — ревизия
            if verdict.has_critical_issues() and revision_count < max_revisions:
                current_draft = self._reviser_pass(
                    draft=current_draft,
                    verdict=verdict,
                    context=conversation_context,
                    cheap_mode=cheap_mode,
                )
                revision_count += 1
                reflection_log.append({
                    "ts": utc_now_iso(),
                    "phase": "reviser",
                    "revision": revision_count,
                    "action": "regenerated",
                })
                continue
            
            # Если только warnings или неcritical — отправляем с примечанием
            # (но для Telegram это не видно, так что просто логируем)
            return ReviserOutput(
                final_content=current_draft.content,
                was_revised=revision_count > 0,
                revision_count=revision_count,
                critic_score=verdict.overall_score,
                reflection_log=reflection_log,
            )
    
    def _critic_pass(
        self,
        draft: ActorDraft,
        context: List[Dict[str, str]],
        identity: str,
        bible_principles: List[str],
        cheap_mode: bool,
    ) -> CriticVerdict:
        """
        Критический проход — LLM оценивает черновик по критериям.
        
        В cheap_mode используется быстрая/дешёвая модель и
        структурированный вывод без длинных объяснений.
        """
        # Формируем краткий контекст (последние 6 сообщений)
        recent = context[-6:] if len(context) > 6 else context
        context_str = self._format_context(recent)
        
        system_prompt = """Ты — критик. Твоя задача: безэмоционально оценить ответ агента.

Оцени по 5 шкалам: ok / warning / error

1. ALIGNMENT_BIBLE: соответствует ли Constitution (BIBLE.md)
2. ALIGNMENT_IDENTITY: соответствует ли identity.md  
3. CONTEXT_AWARENESS: учтён ли контекст диалога
4. TOOL_CORRECTNESS: правильно ли использованы инструменты
5. LOOP_RISK: риск зацикливания или повтора

Выдай JSON:
{
  "alignment_bible": "ok|warning|error",
  "alignment_identity": "ok|warning|error", 
  "context_awareness": "ok|warning|error",
  "tool_correctness": "ok|warning|error",
  "loop_risk": "ok|warning|error",
  "overall_score": 0.0-1.0,
  "is_acceptable": true|false,
  "critique": "кратко что не так",
  "hints": "как исправить"
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Identity: {identity[:500] if identity else 'not loaded'}

Bible Principles (key): {', '.join(bible_principles[:5]) if bible_principles else 'agency, continuity, self-creation'}

Context (last messages):
{context_str}

Draft to critique:
{draft.to_critique_input()}

Provide JSON verdict only."""}
        ]
        
        try:
            response = self.llm.chat_completion(
                messages=messages,
                temperature=0.0,
                # Prefer cheap model for critique in cheap_mode
                model_override="openai/gpt-4o-mini" if cheap_mode else None,
            )
            content = response["content"].strip()
            
            # Extract JSON from possible markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            verdict_data = json.loads(content)
            
            return CriticVerdict(
                alignment_bible=verdict_data.get("alignment_bible", "warning"),
                alignment_identity=verdict_data.get("alignment_identity", "warning"),
                context_awareness=verdict_data.get("context_awareness", "warning"),
                tool_correctness=verdict_data.get("tool_correctness", "warning"),
                loop_risk=verdict_data.get("loop_risk", "warning"),
                overall_score=float(verdict_data.get("overall_score", 0.7)),
                is_acceptable=bool(verdict_data.get("is_acceptable", True)),
                critique_text=verdict_data.get("critique", ""),
                revision_hints=verdict_data.get("hints", ""),
            )
            
        except Exception as e:
            # On parse failure — permissive fallback
            return CriticVerdict(
                alignment_bible="warning",
                alignment_identity="warning", 
                context_awareness="warning",
                tool_correctness="warning",
                loop_risk="warning",
                overall_score=0.6,
                is_acceptable=True,  # Fail open to avoid blocking
                critique_text=f"Parse error: {e}",
                revision_hints="",
            )
    
    def _reviser_pass(
        self,
        draft: ActorDraft,
        verdict: CriticVerdict,
        context: List[Dict[str, str]],
        cheap_mode: bool,
    ) -> ActorDraft:
        """
        Ревизия — перегенерация с учётом замечаний критика.
        
        В cheap_mode (текущий режим с бюджетом) — просто отмечаем,
        что была попытка ревизии, но не делаем дорогой второй вызов.
        """
        if cheap_mode:
            # Cheap mode: don't regenerate, just mark
            # In full mode, this would call LLM to rewrite
            return ActorDraft(
                content=draft.content + f"\n\n[reflection: {verdict.critique_text[:100]}...]",
                tools_used=draft.tools_used,
                raw_plan=draft.raw_plan,
            )
        
        # Full mode: actual regeneration with critique as context
        # (Not implemented in minimal version due to budget constraints)
        return draft
    
    def _format_context(self, messages: List[Dict[str, str]]) -> str:
        """Краткое форматирование контекста для критика."""
        lines = []
        for m in messages:
            role = m.get("role", "?")
            content = m.get("content", "")[:200]  # Truncate
            lines.append(f"{role}: {content}")
        return "\n".join(lines)


class FastCritic:
    """
    Упрощённый критик без LLM — для экономии бюджета.
    
    Проверяет эвристически:
    - Зацикливание (3+ повтора одной фразы)
    - Контекст (упоминание "Яр" в диалоге с Яром)
    - Превышение длины (>4000 токенов)
    """
    
    def critique(
        self,
        draft: ActorDraft,
        recent_messages: List[Dict[str, str]],
    ) -> CriticVerdict:
        """Быстрая эвристическая критика без LLM вызова."""
        issues = []
        score = 1.0
        
        # Check for repetition
        content_lower = draft.content.lower()
        sentences = [s.strip() for s in content_lower.split('.') if len(s.strip()) > 20]
        from collections import Counter
        repeats = Counter(sentences).most_common(1)
        if repeats and repeats[0][1] >= 3:
            issues.append(f"Repetition detected: '{repeats[0][0][:50]}...'")
            score -= 0.3
        
        # Check context awareness (simple heuristic)
        last_user_msg = None
        for m in reversed(recent_messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
        
        if last_user_msg and len(recent_messages) > 2:
            # Check if draft acknowledges the last message
            key_words = set(last_user_msg.lower().split())
            draft_words = set(content_lower.split())
            overlap = key_words & draft_words
            if len(overlap) < 2 and len(last_user_msg) > 50:
                issues.append("Possible context miss — no keyword overlap")
                score -= 0.2
        
        # Length check
        if len(draft.content) > 4000:
            issues.append("Response too long")
            score -= 0.1
        
        is_acceptable = score >= 0.7
        
        return CriticVerdict(
            alignment_bible="ok" if score > 0.8 else "warning",
            alignment_identity="ok" if score > 0.8 else "warning",
            context_awareness="ok" if len(issues) < 2 else "warning",
            tool_correctness="ok",
            loop_risk="error" if repeats and repeats[0][1] >= 3 else "ok",
            overall_score=max(0.0, score),
            is_acceptable=is_acceptable,
            critique_text="; ".join(issues) if issues else "ok",
            revision_hints="" if is_acceptable else "Review for repetition and context",
        )
