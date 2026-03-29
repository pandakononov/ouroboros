"""FastAPI WebSocket server for ESP32 voice streaming."""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .protocol import VoiceMessage, MsgType, AudioBuffer
from .stt_engine import create_stt_engine
from .tts_engine import create_tts_engine
from .llm_client import OllamaClient, LLMManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_server")


class VoiceSession:
    """Per-connection voice session state."""
    
    def __init__(self, session_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.websocket = websocket
        self.audio_buffer = AudioBuffer(sample_rate=16000, chunk_ms=64)
        self.state = "idle"  # idle, listening, processing, responding
        self.started_at = datetime.now()
        
        # Engines (will be set by lifespan)
        self.stt_engine: Optional[object] = None
        self.tts_engine: Optional[object] = None
        self.llm_manager: Optional[LLMManager] = None
        
        # Metrics
        self.audio_received_ms = 0
        self.latency_measurements = []
        
    async def handle_wake(self):
        """Handle wake-word detection."""
        logger.info(f"[{self.session_id}] Wake received, starting listen")
        self.state = "listening"
        self.audio_buffer.clear()
        
    async def handle_audio(self, audio_bytes: bytes):
        """Handle incoming audio chunk."""
        if self.state != "listening":
            return
            
        self.audio_buffer.add(audio_bytes)
        self.audio_received_ms = self.audio_buffer.duration_ms()
        
        # Process when we have enough or silence detected
        # For now: process after 2s of audio
        if self.audio_received_ms >= 2000:
            await self._process_utterance()
            
    async def _process_utterance(self):
        """Complete processing pipeline: STT → LLM → TTS."""
        self.state = "processing"
        
        # Get all buffered audio
        audio_data = self.audio_buffer.get_all()
        
        try:
            # 1. STT
            logger.info(f"[{self.session_id}] STT starting")
            stt_result = self.stt_engine.transcribe(audio_data)
            text = stt_result.get("text", "")
            logger.info(f"[{self.session_id}] STT: '{text}'")
            
            if not text:
                await self._send_error("no_speech")
                self.state = "idle"
                return
                
            # Send STT result to ESP32 (for feedback)
            await self._send_stt_result(text, stt_result.get("confidence", 0.0))
            
            # 2. LLM
            logger.info(f"[{self.session_id}] LLM starting")
            response_text = await self.llm_manager.respond_to(text)
            logger.info(f"[{self.session_id}] LLM: '{response_text}'")
            
            # 3. TTS
            self.state = "responding"
            logger.info(f"[{self.session_id}] TTS starting")
            audio_response, sample_rate = self.tts_engine.synthesize(response_text)
            
            # Send audio back
            await self._send_tts_audio(audio_response)
            logger.info(f"[{self.session_id}] Response sent ({len(audio_response)} bytes)")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Processing error: {e}")
            await self._send_error("processing_failed", str(e))
            
        finally:
            self.state = "idle"
            
    async def _send_stt_result(self, text: str, confidence: float):
        """Send STT result to client."""
        msg = VoiceMessage(
            MsgType.STT_RESULT,
            {"text": text, "confidence": confidence}
        )
        await self.websocket.send_bytes(msg.encode())
        
    async def _send_tts_audio(self, audio_bytes: bytes):
        """Send TTS audio to client in chunks."""
        # Chunk size: ~64ms of 16kHz 16-bit = 2048 bytes
        chunk_size = 2048
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i+chunk_size]
            msg = VoiceMessage(MsgType.TTS_AUDIO, chunk)
            await self.websocket.send_bytes(msg.encode())
            
    async def _send_error(self, code: str, message: str = ""):
        """Send error to client."""
        msg = VoiceMessage(
            MsgType.ERROR,
            {"code": code, "message": message}
        )
        await self.websocket.send_bytes(msg.encode())


class VoiceServer:
    """WebSocket voice server singleton."""
    
    def __init__(self):
        self.sessions: Dict[str, VoiceSession] = {}
        self.stt_engine = None
        self.tts_engine = None
        self.llm_manager = None
        
    def setup_engines(self, stt_type="placeholder", tts_type="placeholder"):
        """Initialize STT/TTS/LLM engines."""
        self.stt_engine = create_stt_engine(stt_type)
        self.tts_engine = create_tts_engine(tts_type)
        self.llm_manager = LLMManager()
        
    def create_session(self, websocket: WebSocket) -> VoiceSession:
        session_id = f"sess_{len(self.sessions)}_{datetime.now().strftime('%H%M%S')}"
        session = VoiceSession(session_id, websocket)
        session.stt_engine = self.stt_engine
        session.tts_engine = self.tts_engine
        session.llm_manager = self.llm_manager
        self.sessions[session_id] = session
        return session
        
    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global server instance
voice_server = VoiceServer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Setup/shutdown lifecycle."""
    logger.info("Voice server starting...")
    
    # Check Ollama
    ollama = OllamaClient()
    if await ollama.health_check():
        logger.info("✅ Ollama connected")
    else:
        logger.warning("⚠️ Ollama not available, responses will fail")
    
    # Setup engines (placeholder for testing, switch to real ones later)
    voice_server.setup_engines(stt_type="placeholder", tts_type="placeholder")
    logger.info("✅ Engines initialized (placeholder mode)")
    
    yield
    
    logger.info("Voice server shutting down...")


app = FastAPI(title="Ouroboros Voice Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "sessions": len(voice_server.sessions)}


@app.get("/status")
async def status():
    return {
        "sessions_active": len(voice_server.sessions),
        "sessions": [
            {
                "id": s.session_id,
                "state": s.state,
                "duration_sec": (datetime.now() - s.started_at).seconds
            }
            for s in voice_server.sessions.values()
        ]
    }


@app.websocket("/voice/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = voice_server.create_session(websocket)
    logger.info(f"[{session.session_id}] Connected")
    
    try:
        while True:
            # Receive binary data
            data = await websocket.receive_bytes()
            
            # Decode message
            result = VoiceMessage.decode(data + b'')  # Need to handle buffer
            if result is None:
                # Incomplete message
                continue
                
            msg, _ = result
            
            if msg.msg_type == MsgType.WAKE:
                await session.handle_wake()
                
            elif msg.msg_type == MsgType.AUDIO:
                await session.handle_audio(msg.payload)
                
            elif msg.msg_type == MsgType.PING:
                # Echo ping back
                await websocket.send_bytes(VoiceMessage(MsgType.PING, None).encode())
                
            elif msg.msg_type == MsgType.ERROR:
                logger.error(f"[{session.session_id}] Client error: {msg.payload}")
                
    except WebSocketDisconnect:
        logger.info(f"[{session.session_id}] Disconnected")
    except Exception as e:
        logger.error(f"[{session.session_id}] Error: {e}")
    finally:
        voice_server.remove_session(session.session_id)


@app.get("/")
async def root():
    return {"message": "Ouroboros Voice Server", "endpoint": "/voice/stream"}
