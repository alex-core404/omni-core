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
            "id": msg.id,
            "from": msg.sender_email,
            "message": decrypt_message(msg.content),
            "created_at": str(msg.created_at),
            "is_read": msg.is_read,
            "reply_to_id": msg.reply_to_id,
            "reply_to_text": decrypt_message(
                db.query(Message).filter(Message.id == msg.reply_to_id).first().content
            ) if msg.reply_to_id else None
        }
        for msg in messages
    ]

@router.get("/unread/{user_email}")
async def get_unread(user_email: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = db.query(Message).filter(
        Message.recipient_email == user_email,
        Message.is_read == False
    ).all()

    counts = {}
    for msg in messages:
        counts[msg.sender_email] = counts.get(msg.sender_email, 0) + 1

    return counts
@router.post("/read/{user_email}/{contact_email}")
async def mark_as_read(user_email: str, contact_email: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    db.query(Message).filter(
        Message.recipient_email == user_email,
        Message.sender_email == contact_email,
        Message.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "ok"}





