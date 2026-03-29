"""Launch script for voice server."""
import argparse
import subprocess
import sys
from pathlib import Path


def check_ollama():
    """Check if Ollama is running."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", [])]
            print(f"✅ Ollama running. Models: {len(models)}")
            return True
    except Exception as e:
        print(f"⚠️ Ollama check failed: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Launch Ouroboros Voice Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9000, help="Port")
    parser.add_argument("--reload", action="store_true", help="Auto-reload")
    parser.add_argument("--stt", default="placeholder", choices=["placeholder", "whisper"])
    parser.add_argument("--tts", default="placeholder", choices=["placeholder", "piper", "kokoro"])
    parser.add_argument("--check-only", action="store_true", help="Check dependencies only")
    
    args = parser.parse_args()
    
    print(f"🎤 Ouroboros Voice Server")
    print(f"   Host: {args.host}:{args.port}")
    print(f"   STT: {args.stt}, TTS: {args.tts}")
    
    check_ollama()
    
    if args.check_only:
        return
    
    # Set env vars for engine selection
    import os
    os.environ["VOICE_STT_ENGINE"] = args.stt
    os.environ["VOICE_TTS_ENGINE"] = args.tts
    
    # Run with uvicorn
    cmd = [
        sys.executable, "-m", "uvicorn",
        "voice_server.main:app",
        "--host", args.host,
        "--port", str(args.port),
        "--log-level", "info"
    ]
    if args.reload:
        cmd.append("--reload")
    
    print(f"\n🚀 Starting server...")
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
