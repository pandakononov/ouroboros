"""Binary protocol for ESP32 ↔ Mac audio streaming.

Message format:
- 1 byte: message type (hex)
- 4 bytes: payload length (big-endian uint32)
- N bytes: payload (raw bytes or JSON)
"""
import struct
import json
from enum import IntEnum
from dataclasses import dataclass
from typing import Union, Optional


class MsgType(IntEnum):
    """Message type identifiers."""
    AUDIO = 0x01        # Raw PCM audio from ESP32
    STT_RESULT = 0x02   # JSON {"text": "...", "conf": 0.95}
    TTS_AUDIO = 0x03    # Raw PCM audio to ESP32
    WAKE = 0x04         # Wake-word detected signal
    PING = 0x05         # Keepalive
    ERROR = 0xFF        # Error report


@dataclass
class VoiceMessage:
    msg_type: MsgType
    payload: Union[bytes, dict, None]
    
    def encode(self) -> bytes:
        """Encode message to binary format."""
        if self.payload is None:
            payload_bytes = b''
        elif isinstance(self.payload, dict):
            payload_bytes = json.dumps(self.payload, ensure_ascii=False).encode('utf-8')
        else:
            payload_bytes = self.payload
            
        header = struct.pack('>BI', self.msg_type.value, len(payload_bytes))
        return header + payload_bytes
    
    @classmethod
    def decode(cls, data: bytes) -> Optional['VoiceMessage']:
        """Decode binary message. Returns None if incomplete."""
        if len(data) < 5:
            return None  # Not enough for header
            
        msg_type_val, payload_len = struct.unpack('>BI', data[:5])
        
        if len(data) < 5 + payload_len:
            return None  # Incomplete payload
            
        payload_bytes = data[5:5+payload_len]
        remain = data[5+payload_len:]
        
        msg_type = MsgType(msg_type_val)
        
        # Decode payload based on type
        if msg_type in (MsgType.STT_RESULT, MsgType.ERROR):
            try:
                payload = json.loads(payload_bytes.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = {"raw": payload_bytes.hex()[:100]}
        elif msg_type in (MsgType.AUDIO, MsgType.TTS_AUDIO):
            payload = payload_bytes
        else:
            payload = payload_bytes if payload_bytes else None
            
        return cls(msg_type=msg_type, payload=payload), remain
    
    def to_dict(self) -> dict:
        """Convert to dict for logging."""
        return {
            "type": self.msg_type.name,
            "payload_preview": str(self.payload)[:100] if self.payload else None
        }


class AudioBuffer:
    """Streaming audio buffer with configurable chunk size."""
    
    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 64):
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self.chunk_samples = int(sample_rate * chunk_ms / 1000)
        self._buffer = bytearray()
        self.bytes_per_sample = 2  # 16-bit
        
    def add(self, data: bytes):
        """Add raw PCM bytes to buffer."""
        self._buffer.extend(data)
        
    def get_chunk(self) -> Optional[bytes]:
        """Get next chunk if available, else None."""
        chunk_size = self.chunk_samples * self.bytes_per_sample
        if len(self._buffer) >= chunk_size:
            chunk = bytes(self._buffer[:chunk_size])
            self._buffer = self._buffer[chunk_size:]
            return chunk
        return None
        
    def get_all(self) -> bytes:
        """Get all remaining data."""
        result = bytes(self._buffer)
        self._buffer.clear()
        return result
        
    def duration_ms(self) -> int:
        """Current buffer duration in milliseconds."""
        return len(self._buffer) * 1000 // (self.sample_rate * self.bytes_per_sample)
        
    def clear(self):
        """Clear buffer."""
        self._buffer.clear()
