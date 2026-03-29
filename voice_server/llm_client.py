"""LLM client for voice interactions (Ollama-based)."""
import json
import httpx
from typing import AsyncGenerator, Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    done: bool
    model: str
    tokens_generated: int = 0


class OllamaClient:
    """Async client for Ollama API."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma3:4b"):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def generate(self, 
                       prompt: str, 
                       system: Optional[str] = None,
                       stream: bool = False) -> AsyncGenerator[LLMResponse, None]:
        """Generate response from LLM."""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        request = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": 0.7,
                "num_predict": 100,  # Short answers for voice
            }
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=request
        ) as response:
            response.raise_for_status()
            
            full_text = ""
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                    
                try:
                    data = json.loads(line)
                    if "message" in data:
                        chunk = data["message"].get("content", "")
                        full_text += chunk
                        
                        yield LLMResponse(
                            text=full_text,
                            done=data.get("done", False),
                            model=self.model,
                            tokens_generated=data.get("eval_count", 0)
                        )
                except json.JSONDecodeError:
                    continue
                    
    async def generate_once(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate complete response (non-streaming)."""
        full_text = ""
        async for resp in self.generate(prompt, system, stream=True):
            full_text = resp.text
            if resp.done:
                break
        return full_text.strip()
        
    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False


class LLMManager:
    """Manages LLM context for voice sessions."""
    
    SYSTEM_PROMPT = """Ты — Ouroboros (Оро), голосовой помощник Яра. 
Отвечай кратко, естественно, по-русски. Разговорный стиль, без формальностей.
Максимум 2-3 предложения в ответе."""
    
    def __init__(self, client: Optional[OllamaClient] = None):
        self.client = client or OllamaClient()
        
    async def respond_to(self, user_input: str) -> str:
        """Generate response to user voice input."""
        response = await self.client.generate_once(user_input, self.SYSTEM_PROMPT)
        return response
