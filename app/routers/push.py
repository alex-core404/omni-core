import os
import json
import base64
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from app.database import get_db
from app.models.push_subscription import PushSubscription
from app.routers.auth import get_current_user

router = APIRouter()

class PushKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscribe(BaseModel):
    endpoint: str
    keys: PushKeys

@router.get("/push/vapid-public")
async def vapid_public(current_user: str = Depends(get_current_user)):
    key = os.getenv("VAPID_PUBLIC_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="На сервере нет VAPID_PUBLIC_KEY")
    return {"public_key": key}

@router.post("/push/subscribe")
async def subscribe(body: PushSubscribe, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    if row:
        row.user_email = current_user
        row.p256dh = body.keys.p256dh
        row.auth = body.keys.auth
    else:
        db.add(PushSubscription(
            user_email=current_user,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth
        ))
    db.commit()
    return {"status": "ok"}

def vapid_der() -> str:
    raw = os.environ["VAPID_PRIVATE_KEY"]
    pad = "=" * ((4 - len(raw) % 4) % 4)
    secret = base64.urlsafe_b64decode(raw + pad)
    key = ec.derive_private_key(int.from_bytes(secret, "big"), ec.SECP256R1())
    der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(der).decode().rstrip("=")

def send_one(sub, payload, private_key):
    from pywebpush import webpush
    webpush(
        subscription_info={
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        },
        data=payload,
        vapid_private_key=private_key,
        vapid_claims={"sub": "mailto:push@omni-core-app.ru"},
    )

async def notify_user(db: Session, user_email: str, title: str, body: str):
    if not user_email or user_email == "ai-bot@omni" or not os.getenv("VAPID_PRIVATE_KEY"):
        return
    rows = db.query(PushSubscription).filter(PushSubscription.user_email == user_email).all()
    if not rows:
        print(f"push skip: no address for {user_email}")
        return
    text = "Файл" if body.startswith("/uploads/") else body.replace("\n", " ")[:180]
    payload = json.dumps({"title": title, "body": text}, ensure_ascii=False)
    private_key = vapid_der()
    from pywebpush import WebPushException
    for row in rows:
        sub = {"endpoint": row.endpoint, "p256dh": row.p256dh, "auth": row.auth}
        try:
            await asyncio.to_thread(send_one, sub, payload, private_key)
            print(f"push sent to {user_email}")
        except WebPushException as exc:
            print(f"push failed: {exc}")
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                db.delete(row)
                db.commit()
        except Exception as exc:
            print(f"push failed: {exc}")

