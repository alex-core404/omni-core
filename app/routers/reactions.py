from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.reaction import Reaction

router = APIRouter()

ALLOWED_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥"]

@router.post("/reactions/{message_id}/{emoji}")
async def add_reaction(
    message_id: int,
    emoji: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if emoji not in ALLOWED_EMOJIS:
        raise HTTPException(status_code=400, detail="Недоступный эмодзи")
    existing = db.query(Reaction).filter(
        Reaction.message_id == message_id,
        Reaction.user_email == current_user
    ).first()

    if existing:
        if existing.emoji == emoji:
            db.delete(existing)
            db.commit()
            return {"status": "removed"}
        else:
            existing.emoji = emoji
            db.commit()
            return {"status": "changed"}

    reaction = Reaction(message_id=message_id, user_email=current_user, emoji=emoji)
    db.add(reaction)
    db.commit()
    return {"status": "added"}

@router.get("/reactions/{message_id}")
async def get_reactions(message_id: int, db: Session = Depends(get_db)):
    reactions = db.query(Reaction).filter(Reaction.message_id == message_id).all()
    counts = {}
    for r in reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
    return counts