import asyncio
import json
import aio_pika
import websockets
import os

connected_clients = set()

async def handle_websocket(websocket):
    connected_clients.add(websocket)
    print(f"[WS] Client connected: {websocket.remote_address}")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)
        print(f"[WS] Client disconnected: {websocket.remote_address}")

async def forward_notifications():
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    print(f"[AMQP] Connecting to RabbitMQ at {rabbitmq_host}...")
    connection = await aio_pika.connect_robust(f"amqp://guest:guest@{rabbitmq_host}/")
    channel = await connection.channel()
    queue = await channel.declare_queue("notifications", durable=True)
    print("[AMQP] Listening to 'notifications' queue.")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                data = message.body.decode()
                print(f"[AMQP] Received: {data}")

                disconnected = []
                for client in connected_clients:
                    try:
                        await client.send(data)
                        print(f"[WS] Sent to {client.remote_address}")
                    except Exception as e:
                        print(f"[WS] Error sending to {client.remote_address}: {e}")
                        disconnected.append(client)

                for client in disconnected:
                    connected_clients.discard(client)

async def main():
    print("[SERVER] Starting WebSocket server on ws://localhost:8005...")
    websocket_server = websockets.serve(handle_websocket, "0.0.0.0", 8005)

    await asyncio.gather(
        websocket_server,
        forward_notifications()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")