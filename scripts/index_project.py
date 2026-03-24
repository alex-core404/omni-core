import asyncio
import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.knowledge import Knowledge
from app.utils.embeddings import get_embedding

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
    print("🚀 Начинаю индексацию проекта...")

    with SessionLocal() as session:
        for file_path in FILES_TO_INDEX:
            if not os.path.exists(file_path):
                print(f"⚠️ Файл не найден: {file_path}")
                continue

            print(f"📖 Читаю {file_path}...")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()   

            vector = await get_embedding(content)

            if vector:
                knowledge = Knowledge(
                    content=content,
                    file_path=file_path,
                    embedding=vector
                )
                session.add(knowledge)
                print(f"✅ Файл {file_path} 'оцифрован'.")

        session.commit()
        print("🎉 Индексация завершена!")
if __name__ == "__main__":
    asyncio.run(index_project())