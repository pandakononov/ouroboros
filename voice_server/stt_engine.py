"""Speech-to-Text engine using Whisper (or placeholder for testing)."""
import time
import wave
import io
from typing import Callable, Optional
from pathlib import Path


class STTEngine:
    """Base STT interface."""
    
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> dict:
        """Transcribe audio bytes to text.
        Returns: {"text": str, "confidence": float}
        """
        raise NotImplementedError
        
    def stream_transcribe(self, chunks: Callable[[], Optional[bytes]], callback: Callable[[dict], None]):
        """Stream audio chunks as they arrive."""
        raise NotImplementedError


class PlaceholderSTT(STTEngine):
    """Mock STT for protocol testing without Whisper."""
    
    def __init__(self, buffer_duration_ms: int = 2000):
        self.buffer_duration_ms = buffer_duration_ms
        
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> dict:
        """Mock transcription with random-ish delay."""
        # Simulate processing time proportional to audio duration
        buffer_duration_ms = len(audio_bytes) * 1000 // (sample_rate * 2)  # 16-bit
        time.sleep(min(buffer_duration_ms / 1000 * 0.05, 0.1))  # Mock latency
        
        # Mock responses for testing
        text = self._classify_mock(audio_bytes)
        
        return {
            "text": text,
            "confidence": 0.85
        }
        
    def _classify_mock(self, audio: bytes) -> str:
        """Mock classification based on audio properties."""
        # Simple heuristic for testing: short audio = "привет", long = "расскажи"
        duration = len(audio) / (16000 * 2)  # seconds
        if duration < 1.0:
            return "привет Оро"
        elif duration < 2.5:
            return "расскажи о себе"
        else:
            return "спасибо за помощь"


class WhisperEngine(STTEngine):
    """Whisper-based STT (requires whisper.cpp or faster-whisper)."""
    
    def __init__(self, model_path: str = "models/ggml-tiny-ru", binary: str = "whisper-cli"):
        self.model_path = Path(model_path)
        self.binary = binary
        self._check_model()
        
    def _check_model(self):
        """Verify model exists."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"Whisper model not found: {self.model_path}")
            
    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> dict:
        """Transcribe using whisper.cpp CLI."""
        import tempfile
        import subprocess
        
        # Write audio to temp WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            with wave.open(f, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                wav.writeframes(audio_bytes)
        
        try:
            # Run whisper
            result = subprocess.run(
                [self.binary, "-m", str(self.model_path), "-f", wav_path, 
                 "--language", "ru", "--output-json"],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            
            if result.returncode == 0:
                # Parse JSON output
                import json
                data = json.loads(result.stdout)
                text = " ".join(seg.get("text", "") for seg in data.get("transcription", []))
                return {"text": text.strip(), "confidence": 0.9}
            else:
                return {"text": "", "confidence": 0.0, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"text": "", "confidence": 0.0, "error": "timeout"}
        except Exception as e:
            return {"text": "", "confidence": 0.0, "error": str(e)}
        finally:
            Path(wav_path).unlink(missing_ok=True)


def create_stt_engine(engine_type: str = "placeholder", **kwargs) -> STTEngine:
    """Factory for STT engines."""
    if engine_type == "placeholder":
        return PlaceholderSTT(**kwargs)
    elif engine_type == "whisper":
        return WhisperEngine(**kwargs)
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
