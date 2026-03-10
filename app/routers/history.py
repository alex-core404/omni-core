from fastapi import APIRouter, Depends, HTTPException
from app.routers.auth import get_current_user
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.message import Message
from app.crypto import decrypt_message

router = APIRouter()

@router.get("/history/{user1}/{user2}")
async def get_history(user1: str, user2: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user not in (user1, user2):
        raise HTTPException(status_code=403, detail="Access denied")
    
    messages = db.query(Message).filter(
        ((Message.sender_email == user1) & (Message.recipient_email == user2)) |
        ((Message.sender_email == user2) & (Message.recipient_email == user1))
    ).order_by(Message.created_at).all()
    
    return [
        {
            "from": msg.sender_email,
            "message": decrypt_message(msg.content),
            "created_at": str(msg.created_at)
        }
        for msg in messages
    ]

