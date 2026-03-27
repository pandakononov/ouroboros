import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def echo(websocket, path):
    logger.info("Client connected")
    try:
        async for message in websocket:
            logger.info(f"Received {len(message)} bytes")
            await websocket.send(message)
    except websockets.ConnectionClosed:
        logger.info("Client disconnected")

async def main():
    async with websockets.serve(echo, "0.0.0.0", 8765):
        logger.info("WebSocket echo server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
