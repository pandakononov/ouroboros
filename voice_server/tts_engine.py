"""Text-to-Speech engine using Kokoro or Piper."""
import time
import io
import wave
from typing import Optional
from pathlib import Path


class TTSEngine:
    """Base TTS interface."""
    
    def synthesize(self, text: str, voice: Optional[str] = None) -> tuple[bytes, int]:
        """Synthesize text to audio.
        Returns: (audio_bytes, sample_rate)
        """
        raise NotImplementedError


class PlaceholderTTS(TTSEngine):
    """Mock TTS for testing - plays tone patterns."""
    
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        
    def synthesize(self, text: str, voice: Optional[str] = None) -> tuple[bytes, int]:
        """Generate sine wave tone with duration proportional to text length."""
        import math
        
        # Duration: ~100ms per char, min 500ms
        char_count = len(text.strip())
        duration_sec = max(0.5, char_count * 0.08)
        num_samples = int(self.sample_rate * duration_sec)
        
        # Generate sine wave at 440 Hz (A4)
        audio = bytearray()
        freq = 440.0
        for i in range(num_samples):
            # Simple sine + some harmonics
            t = i / self.sample_rate
            val = math.sin(2 * math.pi * freq * t) * 0.3
            val += math.sin(2 * math.pi * freq * 2 * t) * 0.1
            
            # Convert to 16-bit PCM
            sample = int(val * 32767)
            audio.extend(sample.to_bytes(2, 'little', signed=True))
            
        # Mock latency simulation
        time.sleep(0.05)
        
        return bytes(audio), self.sample_rate


class PiperTTS(TTSEngine):
    """Piper TTS (ultra-low latency, ~50-80ms)."""
    
    def __init__(self, model_path: str, binary: str = "piper"):
        self.model_path = Path(model_path)
        self.binary = binary
        
    def synthesize(self, text: str, voice: Optional[str] = None) -> tuple[bytes, int]:
        """Synthesize using Piper executable."""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
            
        try:
            # Piper outputs to stdout as WAV
            result = subprocess.run(
                [self.binary, "--model", str(self.model_path), 
                 "--output_file", wav_path, "--text", text],
                capture_output=True,
                timeout=10.0
            )
            
            if result.returncode == 0:
                with wave.open(wav_path, 'rb') as wav:
                    sample_rate = wav.getframerate()
                    audio = wav.readframes(wav.getnframes())
                    return audio, sample_rate
            else:
                raise RuntimeError(f"Piper failed: {result.stderr}")
                
        finally:
            Path(wav_path).unlink(missing_ok=True)


class KokoroTTS(TTSEngine):
    """Kokoro TTS (higher quality, ~150ms)."""
    
    def __init__(self, voice: str = "af_bella"):
        self.voice = voice
        # Lazy import - Kokoro is optional
        self._kokoro = None
        
    def _load(self):
        if self._kokoro is None:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code='ru')
        
    def synthesize(self, text: str, voice: Optional[str] = None) -> tuple[bytes, int]:
        """Synthesize using Kokoro."""
        self._load()
        
        v = voice or self.voice
        audio_chunks = []
        
        # Kokoro returns array of audio chunks
        for _, _, audio in self._pipeline(text, voice=v):
            # Convert numpy to PCM
            audio_int16 = (audio * 32767).astype('int16')
            audio_chunks.append(audio_int16.tobytes())
            
        return b''.join(audio_chunks), 24000  # Kokoro outputs 24kHz


def create_tts_engine(engine_type: str = "placeholder", **kwargs) -> TTSEngine:
    """Factory for TTS engines."""
    if engine_type == "placeholder":
        return PlaceholderTTS(**kwargs)
    elif engine_type == "piper":
        return PiperTTS(**kwargs)
    elif engine_type == "kokoro":
        return KokoroTTS(**kwargs)
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
