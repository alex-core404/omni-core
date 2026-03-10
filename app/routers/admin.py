import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User

router = APIRouter()

ADMIN_KEY = os.getenv("ADMIN_KEY", "omni_admin_2026")

@router.get("/admin/stats")
async def get_stats(key: str, db: Session = Depends(get_db)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    users = db.query(User).all()

    return {
        "users_count": len(users),
        "users": [u.email for u in users]
    }
    
