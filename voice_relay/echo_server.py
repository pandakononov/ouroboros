#!/usr/bin/env python3
"""
Minimal WebSocket relay with echo + test client.

Usage:
    python3 voice_relay/echo_server.py        # start server
    python3 voice_relay/echo_server.py --client  # run test client
"""

import asyncio
import argparse
import wave
import struct
import numpy as np
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call(["pip3", "install", "websockets"])
    import websockets


# =========== CONFIG ===========
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8765
SAMPLE_RATE = 44100
DURATIONSec = 1.0
FREQUENCY = 440.0  # Hz, A4


# =========== ECHO SERVER ===========
async def echo_handler(websocket):
    """Echo back any received audio frame."""
    async for message in websocket:
        # message is bytes (audio chunk)
        await websocket.send(message)  # echo
        print(f"  📡 Server: echoed {len(message)} bytes")


async def start_server():
    async with websockets.serve(echo_handler, SERVER_HOST, SERVER_PORT):
        print(f"🔄 Echo server listening on ws://{SERVER_HOST}:{SERVER_PORT}")
        await asyncio.Future()  # run forever


# =========== TEST CLIENT ===========
def generate_sine_wave(freq: float, duration: float, sr: int) -> bytes:
    """Generate a 16-bit PCM sine wave."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave_data = np.sin(2 * np.pi * freq * t)
    wave_data = (wave_data * 32767).astype(np.int16)
    return wave_data.tobytes()


async def test_client():
    uri = f"ws://127.0.0.1:{SERVER_PORT}"
    print(f"🚀 Test client connecting to {uri} ...")
    try:
        async with websockets.connect(uri) as ws:
            audio_data = generate_sine_wave(FREQUENCY, DURATIONSec, SAMPLE_RATE)
            print(f"  📤 Sending {len(audio_data)} bytes of {FREQUENCY}Hz sine wave...")
            await ws.send(audio_data)
            response = await ws.recv()
            print(f"  📥 Received {len(response)} bytes")
            if response == audio_data:
                print("✅ SUCCESS: Echo matches original data!")
            else:
                print("❌ FAIL: Echo mismatch")
    except Exception as e:
        print(f"❌ Client error: {e}")


# =========== MAIN ===========
def main():
    parser = argparse.ArgumentParser(description="WebSocket Echo Server / Test Client")
    parser.add_argument("--client", action="store_true", help="Run as test client")
    parser.add_argument("--host", default=SERVER_HOST, help="Server host")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Server port")
    args = parser.parse_args()

    if args.client:
        asyncio.run(test_client())
    else:
        print("🔄 Starting echo server...")
        asyncio.run(start_server())


if __name__ == "__main__":
    main()
