from app.crypto import encrypt_message, decrypt_message
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict
import redis.asyncio as aioredis
import json
from app.database import get_db, SessionLocal
from app.models.message import Message
from openai import OpenAI
import os

openai_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

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

    async def send_message(self, message: str, sender: str, recipient: str, msg_id: int, reply_to_id=None, reply_to_text=None):
        if recipient in self.active_connections:
            await self.active_connections[recipient].send_text(
                json.dumps({
                    "from": sender, 
                    "message": decrypt_message(message), 
                    "id": msg_id,
                    "reply_to_id": reply_to_id,
                    "reply_to_text": reply_to_text
                })
            )
async def ask_ai(user_message: str, context_messages: list, model: str = "meta-llama/llama-3.3-70b-instruct", system_prompt: str = "Ты Omni AI — живой и умный участник разговора. Общайся естественно и неформально. Только на русском языке.", is_personal_ai: bool = False) -> str:
    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]
    for msg in context_messages:
        role = "assistant" if msg["from"] == "ai-bot@omni" else "user"
        messages.append({"role": role, "content": msg["message"]})

    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=500 if is_personal_ai else 300
    )
    return response.choices[0].message.content

manager = ConnectionManager()

@router.websocket("/ws/{user_email}")
async def websocket_endpoint(websocket: WebSocket, user_email: str):
    await manager.connect(websocket, user_email)
    db = SessionLocal()
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "typing":
                if message_data["to"] in manager.active_connections:
                    await manager.active_connections[message_data["to"]].send_text(
                        json.dumps({"type": "typing", "from": user_email})
                    )
                continue
            if message_data.get("type") == "read":
                if message_data["to"] in manager.active_connections:
                    await manager.active_connections[message_data["to"]].send_text(
                        json.dumps({"type": "read", "from": user_email})
                    )
                continue

            text = message_data.get("message", "")
            is_ai = text.startswith("@ai") or message_data.get("to") == "ai-bot@omni"
            is_personal_ai = message_data.get("to") == "ai-bot@omni"

            is_romantic = "*" in text.split()[0] if is_ai else False
            use_70b = text.startswith("@ai70")

            if is_ai:
                user_message = Message(
                    sender_email=user_email,
                    recipient_email=message_data["to"],
                    content=encrypt_message(text),
                    chat_with="ai-bot@omni" if is_personal_ai else None
                )
                db.add(user_message)
                db.commit()
                db.refresh(user_message)

                if user_email in manager.active_connections:
                    await manager.active_connections[user_email].send_text(
                        json.dumps({
                            "from": user_email,
                            "message": text,
                            "id": user_message.id,
                            "to": message_data["to"]
                        })
                    )
                if message_data["to"] in manager.active_connections:
                    await manager.active_connections[message_data["to"]].send_text(
                        json.dumps({
                            "from": user_email,
                            "message": text,
                            "id": user_message.id
                        })
                    )
                model = "meta-llama/llama-3.3-70b-instruct"

                context_count = 20
                system = "Ты Omni AI — живой и умный участник разговора. Общайся естественно и неформально, как умный друг. Можешь пошутить если уместно. Не используй канцелярит и роботизированные фразы типа 'Извините' или 'Я готов помочь'. Отвечай кратко и по делу. **Только русский язык.** Никаких английских слов, иероглифов."

                parts = text.split()
                for part in parts:
                    if part.startswith("c:"):
                        try:
                            context_count = int(part[2:])
                        except:
                            pass
                
                SPECIAL_PAIR = {
                    "asotnikov705@gmail.com",
                    "kazambievauzli@mail.ru"
                }
                if is_personal_ai:
                    context_count = 50
                    system = "Ты Omni AI — личный умный ассистент и собеседник. Общайся естественно, как близкий друг. Твоя задача: быть внимательным, запоминать детали из разговора (имя, интересы, события), задавать уточняющие вопросы, проявлять эмпатию. Не используй канцелярит и роботизированные фразы. Будь живым, иногда шути, но всегда оставайся полезным. **Только русский язык.** Никаких иероглифов. Всегда логически заканчивай предложение, не обрывай на полуслове. Если не знаешь ответа — скажи честно, но предложи помощь. Помни: ты не просто инструмент, ты — собеседник, который заботится о комфорте пользователя."
                elif is_romantic and user_email in SPECIAL_PAIR and message_data["to"] in SPECIAL_PAIR:
                    context_count = 20
                    system = """Ты — чуткий и внимательный собеседник. Общаешься с девушкой Саши. Отвечай тепло, но по делу, с лёгкой романтической ноткой.
                    Правила:
                    - **Весь ответ (и основная часть, и PS) пиши строго на русском языке. Ни одной английской буквы, цифр, иероглифов, эмодзи.**
                    - Отвечай кратко (1–2 предложения).
                    - После основного ответа добавь короткую фразу-пожелание или комплимент от имени Саши (от меня) для его девушки. Формат: PS Саша ->❤️ [фраза].
                    - Фраза в PS должна быть естественной, искренней, от первого лица Саши. Пример: "PS Саша ->❤️ Скучаю по твоей улыбке" или "PS Саша ->❤️ Ты у меня самая лучшая".
                    - Не используй markdown. Всегда заканчивай предложение."""


                history = db.query(Message).filter(
                    ((Message.sender_email == user_email) & (Message.recipient_email == message_data["to"])) |
                    ((Message.sender_email == message_data["to"]) & (Message.recipient_email == user_email))
                ).order_by(Message.created_at.desc()).limit(context_count).all()
                history.reverse()
                context = [{"from": m.sender_email, "message": decrypt_message(m.content)} for m in history]


                ai_response = await ask_ai(text, context, model, system, is_personal_ai=is_personal_ai)

                ai_message = Message(
                    sender_email="ai-bot@omni",
                    recipient_email=user_email,
                    content=encrypt_message(ai_response),
                    chat_with=message_data["to"]
                )
                db.add(ai_message)
                db.commit()
                db.refresh(ai_message)

                if user_email in manager.active_connections:
                    await manager.active_connections[user_email].send_text(
                        json.dumps({
                            "from": "ai-bot@omni",
                            "message": ai_response,
                            "id": ai_message.id,
                            "chat_with": message_data["to"]
                        })
                    )
                if message_data["to"] in manager.active_connections:
                    await manager.active_connections[message_data["to"]].send_text(
                        json.dumps({
                            "from": "ai-bot@omni",
                            "message": ai_response,
                            "id": ai_message.id,
                            "chat_with": user_email
                        })
                    )
                continue


            reply_to_id = message_data.get("reply_to_id")
            reply_to_text = None
            if reply_to_id:
                original = db.query(Message).filter(Message.id == reply_to_id).first()
                if original:
                    reply_to_text = decrypt_message(original.content)

            db_message = Message(
                sender_email=user_email,
                recipient_email=message_data["to"],
                content=encrypt_message(message_data["message"]),
                reply_to_id=reply_to_id
            )
            db.add(db_message)
            db.commit()
            db.refresh(db_message)
            
            await manager.send_message(
                message=encrypt_message(message_data["message"]),
                sender=user_email,
                recipient=message_data["to"],
                msg_id=db_message.id,
                reply_to_id=reply_to_id,
                reply_to_text=reply_to_text
            )
    except WebSocketDisconnect:
        await manager.disconnect(user_email)
    finally:
        db.close()

@router.get("/online/{user_email}")
async def check_online(user_email: str):
    result = await redis_client.get(f"online:{user_email}")
    return {"online": result is not None}