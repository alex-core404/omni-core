import asyncio
import os
import sys
import tiktoken


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.knowledge import Knowledge
from app.utils.embeddings import get_embedding

tokenizer = tiktoken.get_encoding("cl100k_base")

def chunk_by_tokens(text, chunk_tokens=800, overlap_tokens=200):
    tokens = tokenizer.encode(text)
    chunks = []
    step = chunk_tokens - overlap_tokens

    for i in range(0, len(tokens), step):
        chunk_tokens_slice = tokens[i:i +chunk_tokens]
        if not chunk_tokens_slice:
            continue
        chunk_text = tokenizer.decode(chunk_tokens_slice)
        chunks.append(chunk_text)

    return chunks

FILES_TO_INDEX = [
    "app/main.py",
    "app/database.py",
    "app/crypto.py",
    "app/routers/auth.py",
    "app/routers/chat.py",
    "app/routers/history.py",
    "app/routers/contacts.py",
    "app/routers/admin.py",
    "app/routers/upload.py",
    "app/routers/reactions.py",
    "app/models/user.py",
    "app/models/message.py",
    "app/models/contact.py",
    "app/models/reaction.py",
    "app/models/knowledge.py",
    "app/utils/embeddings.py",
    "app/schemas/user.py",
    "app/static/index.html",
    "app/static/app.html",
    "app/static/chat.html",
    "app/static/profile.html",
]


async def index_project():
    print("🚀 Начинаю индексацию проекта (чанкинг 800 токенов, overlap 200)...")

    with SessionLocal() as session:
        session.query(Knowledge).delete()
        session.commit()

        for file_path in FILES_TO_INDEX:
            if not os.path.exists(file_path):
                print(f"⚠️ Файл не найден: {file_path}")
                continue

            print(f"📖 Читаю {file_path}...")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()   

            chunks = chunk_by_tokens(content, chunk_tokens=800, overlap_tokens=200)
            print(f"  Разбито на {len(chunks)} чанков")
            
            for i, chunk in enumerate(chunks):
                vector = await get_embedding(chunk)
                if vector:
                    knowledge = Knowledge(
                        content=chunk,
                        file_path=f"{file_path} (часть {i+1})",
                        embedding=vector
                    )
                    session.add(knowledge)
                    print(f"  ✅ Добавлен чанк {i+1}/{len(chunks)}")

        session.commit()
        print("🎉 Индексация завершена!")

if __name__ == "__main__":
    asyncio.run(index_project())