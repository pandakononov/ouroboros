"""
WebSocket Echo Server for Voice Relay Prototype

Minimal server that:
1. accepts PCM audio via WebSocket
2. echoes it back (for testing connectivity)
3. includes a simple test client when run with --client mode

Usage:
    Server:  python voice_relay/echo_server.py
    Client:  python voice_relay/echo_server.py --client
"""

import asyncio
import websockets
import argparse
import struct
import numpy as np


async def echo_handler(websocket):
    """Handle incoming audio and echo it back."""
    print("Client connected")
    try:
        async for message in websocket:
            # message is bytes (PCM audio)
            print(f"Received {len(message)} bytes of audio")
            
            # Echo back the same data
            await websocket.send(message)
            print("Echo sent back")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Client disconnected: {e}")


async def run_server():
    """Start the WebSocket server."""
    async with websockets.serve(echo_handler, "0.0.0.0", 8765):
        print("Echo server running on ws://0.0.0.0:8765")
        print("Waiting for connections...")
        await asyncio.Future()  # Run forever


async def test_client():
    """Simple test client that sends fake PCM data."""
    # Generate 1 second of 16-bit PCM at 16kHz (25600 bytes = 16000 * 2)
    duration_ms = 1000
    sample_rate = 16000
    num_samples = (duration_ms // 1000) * sample_rate
    
    # Create a simple sine wave at 440Hz
    t = np.linspace(0, duration_ms / 1000, num_samples, False)
    frequency = 440
    samples = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM
    pcm_data = (samples * 32767).astype(np.int16).tobytes()
    
    print(f"Generating {len(pcm_data)} bytes of test audio (1s sine wave at 440Hz)")
    
    try:
        async with websockets.connect("ws://localhost:8765") as ws:
            print("Sending test audio...")
            await ws.send(pcm_data)
            
            print("Waiting for echo...")
            response = await ws.recv()
            
            print(f"Received echo: {len(response)} bytes")
            
            if response == pcm_data:
                print("✅ SUCCESS: Echo matches original data!")
            else:
                print("❌ FAIL: Echo differs from original")
                
    except ConnectionRefusedError:
        print("❌ Could not connect to server. Make sure it's running on ws://localhost:8765")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Voice Relay WebSocket Echo Server/Client")
    parser.add_argument("--client", action="store_true", help="Run as test client instead of server")
    args = parser.parse_args()
    
    if args.client:
        print("\n=== Running TEST CLIENT ===\n")
        asyncio.run(test_client())
    else:
        print("\n=== Running SERVER ===\n")
        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            print("\nServer stopped")


if __name__ == "__main__":
    main()
