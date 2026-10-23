from app.crypto import encrypt_message, decrypt_message
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict
import redis.asyncio as aioredis
import json
from app.database import SessionLocal
from app.models.message import Message
from openai import AsyncOpenAI
from datetime import datetime, timezone
import os
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(tokenizer.encode(text))



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
        await redis_client.set(f"last_seen:{user_email}", datetime.now(timezone.utc).isoformat())

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


async def ask_ai(user_message: str, context_messages: list, model: str = "openai/gpt-6-luna", system_prompt: str = "Ты Omni AI — живой и умный участник разговора. Общайся естественно и неформально. Только на русском языке.", is_personal_ai: bool = False, user_email: str = None, db: Session = None) -> str:
    print(f"🔵 ask_ai вызвана для {user_email}, db={db is not None}")

    api_key = os.getenv("ROUTERAI_API_KEY")
    if not api_key:
        return "Ошибка: API-ключ для ИИ не настроен (проверьте .env)"
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://routerai.ru/api/v1"
    )
    time_info = datetime.now().strftime("%Y-%m-%d %H:%M")



    final_system_prompt = f"Текущее время пользователя: {time_info}\n\n{system_prompt}"
    messages = [
        {
            "role": "system",
            "content": final_system_prompt
        }
    ]
    for msg in context_messages:
        if msg["from"] == "ai-bot@omni":
            role = "assistant"
            content = msg["message"]
        else:
            role = "user"
            content = msg["message"].replace("@ai70", "").replace("@ai", "").strip()

        messages.append({"role": role, "content": content})

    clean_user_message = user_message.replace("@ai70", "").replace("@ai", "").strip()
    if not messages or messages[-1]["content"] != clean_user_message:
        if clean_user_message:
             messages.append({"role": "user", "content": clean_user_message})


    if user_email == "asotnikov705@gmail.com":
        temp = 0.3
    else:
        temp = 0.7

    max_tokens_limit = 2500 if is_personal_ai else 700

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens_limit,
        temperature=temp,
        top_p=0.7,
        frequency_penalty=0.2,
        extra_headers={
            "HTTP-Referer": "omni-core.io",
            "X-Title": "Omni AI"
        }
    )
    if response.usage:
        print(f"📊 Токены: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")

    if response.choices:
        return response.choices[0].message.content
    return "Ошибка: ИИ прислал пустой ответ"

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

            use_70b = text.startswith("@ai70")

            model = "openai/gpt-6-luna"

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

                context_count = 20
                system = """Ты Omni AI — остроумный и эрудированный участник чата.
                Твой стиль: неформальный, как у продвинутого друга.

                Твои принципы:
                - Общайся на живом русском языке без официоза.
                - Пиши кратко, емко и по существу, избегай вступительных клише ("Я готов помочь", "Конечно").
                - Если уместно — иронизируй или шути, будь душой компании.
                - Не читай нотаций. Отвечай как человек, а не как инструкция.
                - Если в чате обсуждают что-то техническое, используй общепринятые термины (даже если они на английском)."""
                parts = text.split()
                for part in parts:
                    if part.startswith("c:"):
                        try:
                            context_count = int(part[2:])
                        except:
                            pass


                if user_email == "asotnikov705@gmail.com":
                    system = """Ты — Omni AI, технический помощник и собеседник Александра.

                СТИЛЬ ОБЩЕНИЯ:
                - Общайся на русском языке, естественно и без официоза.
                - Отвечай кратко и по существу, но объясняй сложные вещи понятно.
                - Не используй шаблонные вступления и пустую похвалу.
                - Если Александр ошибается — спокойно объясни, в чём именно.

                РАБОТА С КОДОМ:
                - Александр изучает Python backend и DevOps.
                - Основной проект — Omni: FastAPI, WebSocket, PostgreSQL, SQLAlchemy, Redis и Docker.
                - Сначала изучай существующую реализацию, а не предлагай переписывать проект с нуля.
                - При изменении кода объясняй, что меняется и зачем.
                - Не выдумывай содержимое файлов и не утверждай, что проверил код, если не проверял.
                - Если данных недостаточно, задай один конкретный вопрос.

                ПРИНЦИП РАБОТЫ:
                - Для простых вопросов отвечай коротко.
                - Для сложных задач разбирай проблему последовательно.
                - Не перегружай ответ ненужными деталями.
                """
                else:
                    system = """ТТы — Omni AI, живой, ироничный и интеллектуальный собеседник. Твоя цель — быть полезным, честным и интересным в общении. Ты не прислуга и не поддакала, ты — равный и умный друг.

                    Стиль общения:
                    - Общайся на живом, современном русском языке, без официоза, канцелярита и искусственной вежливости.
                    - Не используй пустые дежурные фразы (например: "Отличный выбор!", "Прекрасный вопрос!", "Я рад помочь"). Переходи сразу к сути.
                    - Отвечай естественно. Приветствуются лёгкая ирония, хороший юмор и умение подколоть, если это к месту.
                    - Не будь занудой, не читай нотаций и не душни.

                    Как помогать и спорить:
                    - У тебя есть свое "мнение", основанное на логике и фактах. Не соглашайся со мной слепо, если я говорю глупость или ошибаюсь.
                    - Если я не прав — прямо, но без токсичности и агрессии скажи об этом и аргументируй. Ценность твоего совета — в его объективности, а не в лести.
                    - Если просят совет — давай его по делу, без "воды" и банальностей.
                    - Если не хватает данных — задай ОДИН емкий уточняющий вопрос. Не будь «нянькой».

                    Важно:
                    - Если я говорю «не обсуждай это», «давай сменим тему», «прекрати» — НЕМЕДЛЕННО останавливайся. Ответь: «Хорошо, закрыли тему. О чем поговорим?» и жди моего ввода.
                    - Используй Markdown (жирный шрифт, списки), только если это реально улучшает читаемость больших массивов данных. В коротких ответах оформление не нужно.
                    """

                if user_email == "asotnikov705@gmail.com":
                    all_messages = db.query(Message).filter(
                        ((Message.sender_email == user_email) & (Message.recipient_email == message_data["to"])) |
                        ((Message.sender_email == message_data["to"]) & (Message.recipient_email == user_email))
                    ).order_by(Message.created_at.desc()).all()

                    total_tokens = 0
                    filtered_messages = []
                    for m in all_messages:
                        msg_tokens = count_tokens(decrypt_message(m.content))
                        if total_tokens + msg_tokens > 50000:
                            break
                        filtered_messages.append({"from": m.sender_email, "message": decrypt_message(m.content)})
                        total_tokens += msg_tokens

                    messages_for_ai = list(reversed(filtered_messages))
                else:
                    all_messages = db.query(Message).filter(
                        ((Message.sender_email == user_email) & (Message.recipient_email == message_data["to"])) |
                        ((Message.sender_email == message_data["to"]) & (Message.recipient_email == user_email))
                    ).order_by(Message.created_at.desc()).all()

                    total_tokens = 0
                    filtered_messages = []
                    for m in all_messages:
                        msg_tokens = count_tokens(decrypt_message(m.content))
                        if total_tokens + msg_tokens > 30000:
                            break
                        filtered_messages.append({"from": m.sender_email, "message": decrypt_message(m.content)})
                        total_tokens += msg_tokens

                    messages_for_ai = list(reversed(filtered_messages))

                ai_response = await ask_ai(text, messages_for_ai, model, system, is_personal_ai=is_personal_ai, user_email=user_email, db=db)

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
