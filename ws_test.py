import asyncio
import websockets


async def main():
    uri = "ws://localhost:8000/ws/buses"
    async with websockets.connect(uri) as websocket:
        while True:
            msg = await websocket.recv()
            print(msg)

asyncio.run(main())
