from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.message import Message
from app.crypto import decrypt_message

router = APIRouter()

@router.get("/history/{user1}/{user2}")
async def get_history(user1: str, user2: str, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(
        ((Message.sender_email == user1) & (Message.recipient_email == user2)) |
        ((Message.sender_email == user2) & (Message.recipient_email == user1))
    ).order_by(Message.created_at).all()    
    
    return [
        {
            "from": msg.sender_email,
            "message": decrypt_message(msg.content),
            "created_at": msg.created_at
        }
        for msg in messages
    ]

