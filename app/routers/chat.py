from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict
import redis.asyncio as aioredis
import json
from app.database import get_db
from app.models.message import Message

router = APIRouter()

redis_client = aioredis.from_url("redis://localhost:6379")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_email: str):
        await websocket.accept()
        self.active_connections[user_email] = websocket
        await redis_client.set(f"online:{user_email}", "1")

    async def disconnect(self, user_email: str):
        self.active_connections.pop(user_email, None)
        await redis_client.delete(f"online:{user_email}")

    async def send_message(self, message: str, sender: str, recipient: str):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_text(
                json.dumps({"from": sender, "message": message})
            )

manager = ConnectionManager()

@router.websocket("/ws/{user_email}")
async def websocket_endpoint(websocket: WebSocket, user_email: str, db: Session = Depends(get_db)):
    await manager.connect(websocket, user_email)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            db_message = Message(
                sender_email=user_email,
                recipient_email=message_data["to"],
                content=message_data["message"]
            )
            db.add(db_message)
            db.commit()
            
            await manager.send_message(
                message=message_data["message"],
                sender=user_email,
                recipient=message_data["to"]
            )
    except WebSocketDisconnect:
        await manager.disconnect(user_email)