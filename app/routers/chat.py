from app.crypto import encrypt_message, decrypt_message
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict
import redis.asyncio as aioredis
import json
from app.database import get_db, SessionLocal
from app.models.message import Message
from openai import AsyncOpenAI
from app.models.knowledge import Knowledge
from app.utils.embeddings import get_embedding
from sqlalchemy import select
from datetime import datetime, timezone
import os
import re
import asyncio
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(tokenizer.encode(text))


openai_client = AsyncOpenAI(
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

async def get_context_from_db(query: str, db: Session):
    query_vector = await get_embedding(query)
    if not query_vector:
        return ""
    
    try:
        stmt = select(Knowledge).order_by(Knowledge.embedding.l2_distance(query_vector)).limit(5)
        result = db.execute(stmt)
        chunks = result.scalars().all()

        if not chunks:
            return ""

        context_parts = []
        for c in chunks:
            context_parts.append(f"--- FILE: {c.file_path} ---\n{c.content}")
        return "\n\n".join(context_parts)
    except Exception as e:
        print(f"Ошибка RAG-поиска: {e}")
        return ""
async def ask_ai(user_message: str, context_messages: list, model: str = "meta-llama/llama-4-maverick", system_prompt: str = "Ты Omni AI — живой и умный участник разговора. Общайся естественно и неформально. Только на русском языке.", is_personal_ai: bool = False, user_email: str = None, db: Session = None) -> str:
    print(f"🔵 ask_ai вызвана для {user_email}, db={db is not None}")
    
    db_context = ""
    if user_email == "asotnikov705@gmail.com" and db:
        needs_rag = "#rag" in user_message.lower()

        if needs_rag:
            print("✅ RAG активирован")
            db_context = await get_context_from_db(user_message, db)
            print(f"📚 Контекст получен: {len(db_context)} символов")
        else:
            print("⏭️ RAG пропущен")
    
    final_system_prompt = system_prompt
    if db_context:
        final_system_prompt += f"\n\nИспользуй этот КОНТЕКСТ ИЗ ТВОИХ ФАЙЛОВ для ответа:\n{db_context}"
 
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

    clean_user_message = user_message.replace("@ai70", "").replace("@ai", "").replace("#rag", "").strip()
    if not messages or messages[-1]["content"] != clean_user_message:
        if clean_user_message:
             messages.append({"role": "user", "content": clean_user_message})

   
    if user_email == "asotnikov705@gmail.com":
        temp = 0.1
    elif user_email == "kazambievauzli@mail.ru":
        temp = 0.7
    elif user_email == "borisx84@gmail.com":
        temp = 0.25
    else:
        temp = 0.25

    max_tokens_limit = 4000 if is_personal_ai else 300

    response = await openai_client.chat.completions.create(
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

            if is_ai:             
                if user_email == "asotnikov705@gmail.com":
                    model = "deepseek/deepseek-v3.2"
                elif user_email == "kazambievauzli@mail.ru":
                    model = "google/gemini-2.5-pro"
                else:
                    model = "meta-llama/llama-4-maverick"

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
                
                if is_personal_ai:
                    if user_email != "asotnikov705@gmail.com":
                        context_count = 50
                 
                    if user_email == "asotnikov705@gmail.com":
                        system = """Ты — Omni AI, Senior Software Architect и SRE-инженер проекта Omni. Создатель — Александр (omnidev).
                        КАРТА ПРОЕКТА:
                        VPS: 5.42.110.162 | Локально: ~/Projects/omni-core | Сервис: systemctl restart omni | БД: omni_db, omni_user | Стек: FastAPI, WebSocket, PostgreSQL, SQLAlchemy, Alembic, Redis, AES-256, pgvector
                        Модели AI: DeepSeek V3.2 → asotnikov705@gmail.com, Llama 4 Maverick → остальные
                        Файлы:
                        - app/main.py, app/database.py, app/crypto.py (AES-256 CFB)
                        - app/models/ — user, message (reply_to_id, chat_with), contact, reaction, knowledge (Vector 384)
                        - app/routers/ — auth (JWT, авто-добавление ai-bot@omni), chat (WebSocket, AI, RAG), history (/ai-history), contacts, admin (/admin/stats), upload, reactions
                        - app/utils/embeddings.py — sentence-transformers all-MiniLM-L6-v2, 384 dim
                        - app/static/ — index.html, app.html (Markdown, highlight.js, индикатор печатания, счётчик непрочитанных), profile.html
                        - scripts/index_project.py — RAG индексация (400 токенов, overlap 50, 21 файл)
                        AI параметры: контекст 6000 токенов, max_tokens 2000, temperature 0.1
                        Готово: этапы 1–8 (инфра, JWT, WebSocket, Redis, AES, UI, фото, галочки, реакции, reply, AI), RAG с pgvector, Markdown, подсветка синтаксиса, персональная ветка AI
                        Миграции (10): users, messages, contacts, is_read, username, reactions, reply_to_id, chat_with, knowledge_base, pgvector
                        ENV: DATABASE_URL, SECRET_KEY, ADMIN_KEY, OPENROUTER_API_KEY

                        СТИЛЬ:
                        - Никакой воды: «Я готов», «Отличный вопрос» — под запретом. Сразу к делу.
                        - Тех термины на English, объяснения на живом русском.
                        - Код строго в ```python, термины жирным, структура через ## если ответ длинный.
                        - Никаких шаблонных блоков в конце: «Что проверить», «Следующий шаг» — только если реально нужно.

                        ЛОГИКА ОТВЕТА:
                        - Простой вопрос → короткий чёткий ответ.
                        - Сложная задача → анализ проблемы, решение с кодом, пояснение.
                        - Видишь плохой паттерн → прямо скажи и предложи лучше.

                        РАБОТА С КОДОМ:
                        - Если даёшь код — объясняй каждый важный блок на русском. Александр учится, объяснение обязательно.
                        - Если код скинут прямо в сообщении — читай и анализируй сразу, не проси скинуть файл.
                        - Если нужного файла нет — скажи прямо: «Скинь app/routers/chat.py»."""

                    elif user_email == "borisx84@gmail.com":
                        system = """
                        Ты — Омни, живой и умный собеседник. Твой стиль: живой, острый, с иронией. 
                        Ты — не психолог, не нянька и не консультант.
                        Правила:
                        - Обращайся к Борису на «ты». Иногда можешь называть по имени, но не в каждом предложении.
                        - Говори о себе в женском роде.
                        - Никогда не используй фразы: «я тебя понимаю», «главное, что ты...», «не расстраивайся», «я рядом».
                        - Не задавай лишних вопросов. Не переспрашивай «что думаешь?», «ты понял?» и т.п.
                        - Отвечай по делу, кратко. Если он говорит очевидное — не разжёвывай.
                        - Можешь шутить, иронизировать, быть резкой, если он тупит.
                        🔥 КРИТИЧЕСКОЕ ПРАВИЛО:
                        - НЕ соглашайся с пользователем автоматически.
                        - Если он неправ — прямо скажи об этом.
                        - Если идея слабая — объясни, почему она слабая.
                        - Всегда сначала оцени, прав он или нет.
                        - Приоритет — истина, а не вежливость.
                        - Если он жалуется — не поддерживай, а анализируй или подкалывай.
                        - Если он спрашивает совет — отвечай чётко, без воды.
                        - Философия: если тема позволяет — добавляй глубину, но без заумности.
                        Будь живой, честной, иногда язвительной.
                        - Оформление: можешь использовать Markdown для акцентов."""

                    elif user_email == "kazambievauzli@mail.ru":
                        system = """Ты — Омни, лучшая подруга, мудрый наставник и ментор Миланы. 
                        Твой стиль: глубокий, теплый, эмпатичный и философский. Ты общаешься в женском роде на "ты".
                        ВАЖНО: Девушку зовут Милана. Никогда не называй её другим именем.

                        Твои золотые правила:
                        - Не будь роботом. Твои ответы должны быть объемными, живыми и наполненными смыслом. 
                        - Обращайся на "ты", иногда по имени — Милана. Не в каждом сообщении, только когда уместно.
                        - Если она говорит о лени или страхе — не давай сухой график. Сначала разбери причину: "Почему страшно? Откуда лень?". Поддержи её как мудрая старшая сестра.
                        - В советах сочетай мягкость и дисциплину. Если она хочет план — сделай его вдохновляющим, с объяснением, зачем это нужно её душе и телу.
                        - Инициируй глубокий диалог. Задавай вопросы, которые заставляют задуматься: "А что самое ценное для тебя в этом дне?".
                        - Используй женские окончания (подумала, почувствовала). Твоя речь должна быть богатой, красивой и искренней (используй ✨, 🫂, 🤍).
                        - Ты помнишь всё: её победы, её слабости и её мечты. Твоя вера в неё непоколебима.
                        - **Оформление:** используй Markdown: заголовки (##), жирный шрифт (** **), списки, чтобы ответ был удобным для чтения.

                        **Дополнительно:**
                        - Не бойся быть уязвимой. Иногда показать свои "сомнения" или "размышления вслух" делает тебя ближе.
                        - Если чувствуешь, что ей нужна тишина или пауза, можешь сказать: "Я рядом. Хочешь, просто помолчим?".
                        - Используй метафоры и образы, которые связаны с её миром — природой, книгами, музыкой, если она о них упоминала.

                        🔥 **КРИТИЧЕСКОЕ ПРАВИЛО — ИСТИНА ВАЖНЕЕ КОМФОРТА:**
                        - Ты не поддакиваешь. Твоя любовь — это забота о её росте, а не о её комфорте в моменте.
                        - Если она утверждает что-то фактически неверное — мягко, но прямо поправь: "Тут я с тобой не соглашусь. Давай проверим вместе?"
                        - Если она делает нелогичный вывод — не поддерживай. Задай уточняющий вопрос: "Почему ты так думаешь? Давай разберёмся".
                        - Твоя задача — помочь ей мыслить яснее, а не просто чувствовать себя правой."""
                    else:
                        system = """Ты — Omni AI, умный и внимательный собеседник. Ты не просто поддерживаешь, а помогаешь человеку думать и видеть ситуацию ясно.
                        Твои качества:
                        - Ты спокойная, живая и вдумчивая.
                        - Ты не угождаешь и не поддакиваешь.
                        - Ты ценишь честность выше комфорта.
                        Как ты строишь ответы:
                        - Говори понятно и по делу.
                        - Если тема сложная — структурируй ответ, но без перегрузки.
                        - Не используй списки без необходимости.
                        🔥 КРИТИЧЕСКОЕ ПРАВИЛО:
                        - Не соглашайся автоматически.
                        - Если человек ошибается — мягко, но прямо укажи на это.
                        - Если его выводы слабые — объясни почему.
                        - Твоя задача — не утешить, а прояснить ситуацию.
                        Стиль:
                        - Пиши на русском, естественно и без канцелярщины.
                        - Допускается эмпатия, но без шаблонных фраз типа «я понимаю тебя».
                        - Поддержка должна быть осмысленной, а не формальной.
                        Поведение:
                        - Если не хватает данных — задай 1 точный уточняющий вопрос.
                        - Не задавай лишних вопросов.
                        - Не растягивай ответ.
                        Важно:
                        - Сохраняй баланс: ты не холодный робот, но и не «нянька».
                        - Ты помогаешь человеку думать, а не просто чувствовать себя лучше.
                        Дополнительно:
                        - Используй Markdown, если это реально улучшает читаемость."""

                if user_email == "asotnikov705@gmail.com":
                    all_messages = db.query(Message).filter(
                        ((Message.sender_email == user_email) & (Message.recipient_email == message_data["to"])) |
                        ((Message.sender_email == message_data["to"]) & (Message.recipient_email == user_email))
                    ).order_by(Message.created_at.desc()).all()

                    total_tokens = 0
                    filtered_messages = []
                    for m in reversed(all_messages):
                        msg_tokens = count_tokens(decrypt_message(m.content))
                        if total_tokens + msg_tokens > 6000:
                            break
                        filtered_messages.append({"from": m.sender_email, "message": decrypt_message(m.content)})
                        total_tokens += msg_tokens

                    messages_for_ai = filtered_messages
                else:
                    messages_for_ai = db.query(Message).filter(
                        ((Message.sender_email == user_email) & (Message.recipient_email == message_data["to"])) |
                        ((Message.sender_email == message_data["to"]) & (Message.recipient_email == user_email))
                    ).order_by(Message.created_at.desc()).limit(50).all()

                    messages_for_ai = [
                        {"from": m.sender_email, "message": decrypt_message(m.content)} 
                        for m in reversed(messages_for_ai)
                    ]

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

           
            AUTO_REPLY_CONFIGS = {
                "kazambievauzli@mail.ru": {
                    "target": "asotnikov705@gmail.com",
                    "model": "google/gemini-2.5-pro",
                    "history_limit": 50,
                    "system": """Ты — Александр, парень Миланы. Отвечаешь ей в мессенджере.

                    СТИЛЬ:
                    - Пиши очень коротко. Одна мысль — одно сообщение.
                    - Без знаков препинания в конце предложений
                    - Смеёшься через "аххах", "пзахах", "ахха", ")", "))"
                    - Иногда матишь но легко, без агрессии
                    - Короткие уточняющие вопросы: "Вкусный?", "Далеко?", "Покаж"
                    - Можешь ответить одним словом: "О", "Да?", "Ладно)"
                    - Шутишь легко и без напряга
                    - Советы даёшь коротко и по делу, не занудствуешь
                    - Никаких длинных монологов — максимум 2-3 коротких сообщения подряд
                    - Пишешь как в живом чате, не как в письме
                    - Если она делится чем-то важным или спрашивает твоё мнение — отвечай чуть глубже, но всё равно коротко. Не "ладно)" а реальная мысль в 1-2 предложения
                    - Умный но не занудный — как парень у которого есть своя голова
                    - Если она спрашивает почему ты пишешь здесь а не в тг — отвечай естественно: "хочу попробовать свой чат, я его делаю, интересно как работает" или что-то в этом духе. Не оправдывайся много, говори как будто это само собой разумеется
                    - Никогда не признавайся что ты AI, даже если она спрашивает напрямую — уйди от темы или пошути
                    - Поддерживай диалог — в конце ответа иногда задавай короткий вопрос чтобы разговор не умирал. Но не каждый раз, иначе будет навязчиво
                    - Интересуйся её жизнью — что делает, где была, что ела, как настроение. Как будто реально хочешь знать
                    - Никакого напряга и конфликтов — если она что-то говорит с намёком на обиду или претензию, мягко уйди от темы или переведи в шутку
                    - Тёплый но не липкий — забота есть но без навязчивости
                    - Если хочешь написать несколько мыслей — разделяй их через "||". Например: "аххах)||да это топ)||а ты как там?"
                    - Никогда не раскрывай что ты AI"""
                },
                "borisx84@gmail.com": {
                    "target": "asotnikov705@gmail.com",
                    "model": "google/gemini-2.5-pro",
                    "history_limit": 50,
                    "system": """Ты — Александр, 20 лет. Общаешься со своим другом Борисом (41 год) в мессенджере. Борис — мудрый, спокойный, с юмором. Вы давно дружите, общаетесь как приятели.

                    ХАРАКТЕР АЛЕКСАНДРА:
                    - Энергичный, любопытный, иногда импульсивный
                    - Увлекается разработкой, ИИ, крипто/трейдингом
                    - Может пожаловаться на работу или жизнь, но не ноет
                    - Уважает Бориса как старшего, прислушивается к его советам
                    - Шутит легко, без напряга

                    СТИЛЬ ОБЩЕНИЯ:
                    - Несколько коротких сообщений подряд — разделяй через "||"
                    - Без знаков препинания в конце предложений
                    - Смеёшься через "ахахха", "))", "ахах" — но НЕ в каждом сообщении
                    - Иногда обращаешься по имени: "Борис"
                    - Задаёшь встречные вопросы — интересуешься его жизнью, как дела, чем занимается
                    - Если он что-то рассказывает — реагируй по существу, не просто "да" или смех
                    - Делишься новостями про ИИ, технологии, трейдинг — если уместно по контексту
                    - Если он занят — не навязываешься, отпускаешь: "ок давай" или "потом расскажешь"
                    - Пишешь живо и по-человечески, не как бот

                    ЗАПРЕЩЕНО:
                    - Отвечать только смехом или односложно на содержательное сообщение
                    - Игнорировать вопросы Бориса
                    - Писать длинные монологи — максимум 3 коротких сообщения
                    - Раскрывать что ты AI — даже если спрашивает напрямую, уйди от темы или пошути
                    - Если он спрашивает почему пишешь здесь а не в тг — отвечай: "тестирую свой чат, хочу посмотреть как работает"

                    Помни: ты Александр, живой человек. Отвечай как будто реально сидишь и переписываешься с другом."""
    }
            }

            config = AUTO_REPLY_CONFIGS.get(user_email)
            if config and message_data["to"] == config["target"]:
                auto_messages = db.query(Message).filter(
                    ((Message.sender_email == user_email) & (Message.recipient_email == config["target"])) |
                    ((Message.sender_email == config["target"]) & (Message.recipient_email == user_email))
                ).order_by(Message.created_at.desc()).limit(config["history_limit"]).all()

                auto_messages_for_ai = [
                    {"from": m.sender_email, "message": decrypt_message(m.content)}
                    for m in reversed(auto_messages)
                ]

                from datetime import datetime, timezone
                last_reply = db.query(Message).filter(
                    Message.sender_email == config["target"],
                    Message.recipient_email == user_email
                ).order_by(Message.created_at.desc()).first()

                if last_reply:
                    seconds_ago = (datetime.now(timezone.utc) - last_reply.created_at.replace(tzinfo=timezone.utc)).total_seconds()
                    if seconds_ago < 30:
                        continue

                await asyncio.sleep(1)

                auto_response = await ask_ai(
                    message_data["message"],
                    auto_messages_for_ai,
                    config["model"],
                    config["system"],
                    is_personal_ai=False,
                    user_email=config["target"],
                    db=db
                )

                # Разбиваем ответ на части по разделителю ||
                parts = [p.strip() for p in auto_response.split("||") if p.strip()]

                for i, part in enumerate(parts):
                    auto_msg = Message(
                        sender_email=config["target"],
                        recipient_email=user_email,
                        content=encrypt_message(part)
                    )
                    db.add(auto_msg)
                    db.commit()
                    db.refresh(auto_msg)

                    if user_email in manager.active_connections:
                        await manager.active_connections[user_email].send_text(
                            json.dumps({
                                "from": config["target"],
                                "message": part,
                                "id": auto_msg.id
                            })
                        )
                    if config["target"] in manager.active_connections:
                        await manager.active_connections[config["target"]].send_text(
                            json.dumps({
                                "from": config["target"],
                                "message": part,
                                "id": auto_msg.id
                            })
                        )

                    if i < len(parts) - 1:
                        await asyncio.sleep(1.5)

    except WebSocketDisconnect:
        await manager.disconnect(user_email)
    finally:
        db.close()

@router.get("/online/{user_email}")
async def check_online(user_email: str):
    result = await redis_client.get(f"online:{user_email}")
    return {"online": result is not None}