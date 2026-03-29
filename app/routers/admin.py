import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.message import Message
import redis.asyncio as aioredis

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY", "omni_admin_2026")
redis_client = aioredis.from_url("redis://localhost:6379")

@router.get("/admin/stats")
async def get_stats(key: str, db: Session = Depends(get_db)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    users = db.query(User).all()
    result = []

    for u in users:
        is_online = await redis_client.get(f"online:{u.email}")
        last_seen_raw = await redis_client.get(f"last_seen:{u.email}")
        last_seen = last_seen_raw.decode() if last_seen_raw else None

        result.append({
            "email": u.email,
            "username": u.username,
            "online": bool(is_online),
            "last_seen": last_seen
        })

    return {
        "users_count": len(users),
        "users": result
    }

@router.delete("/admin/user/{user_email}")
async def delete_user(user_email: str, key: str, db: Session = Depends(get_db)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(Message).filter(
        (Message.sender_email == user_email) |
        (Message.recipient_email == user_email)
    ).delete()
    db.delete(user)
    db.commit()

    return {"status": "deleted", "email": user_email}

@router.delete("/admin/messages/{user_email}")
async def clear_user_messages(user_email: str, key: str, db: Session = Depends(get_db)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    deleted = db.query(Message).filter(
        (Message.sender_email == user_email) |
        (Message.recipient_email == user_email)
    ).delete()
    db.commit()

    return {"status": "cleared", "deleted_count": deleted}