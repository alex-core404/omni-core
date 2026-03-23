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
    "app/routers/chat.py",
    "app/static/app.html" 
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