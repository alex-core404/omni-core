from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.contact import Contact
from app.routers.auth import get_current_user

router = APIRouter()

@router.post("/contacts/add")
async def add_contact(owner_email: str, contact_email: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user != owner_email:
        raise HTTPException(status_code=403, detail="Access denied")
    existing = db.query(Contact).filter(
        Contact.owner_email == owner_email,
        Contact.contact_email == contact_email
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Контакт уже добавлен")
    contact = Contact(owner_email=owner_email, contact_email=contact_email)
    db.add(contact)
    db.commit()
    return {"status": "ok"}

@router.get("/contacts/{owner_email}")
async def get_contacts(owner_email: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user != owner_email:
        raise HTTPException(status_code=403, detail="Access denied")
    from app.models.user import User
    contacts = db.query(Contact).filter(
        Contact.owner_email == owner_email
    ).all()
    result = []
    for c in contacts:
        user = db.query(User).filter(User.email == c.contact_email).first()
        result.append({
            "email": c.contact_email,
            "username": user.username if user and user.username else c.contact_email
        })
    return result

@router.delete("/contacts/delete")
async def delete_contact(owner_email: str, contact_email: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user != owner_email:
        raise HTTPException(status_code=403, detail="Access denied")
    contact = db.query(Contact).filter(
        Contact.owner_email == owner_email,
        Contact.contact_email == contact_email
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Контакт не найден")
    db.delete(contact)
    db.commit()
    return {"status": "ok"}

    