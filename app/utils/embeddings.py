import openai
import os
from dotenv import load_dotenv

load_dotenv()

client = openai.AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)
async def get_embedding(text: str) -> list[float]:
    try:
        clean_text = text.replace("\n", " ").strip()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=[clean_text]
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Ошибка при создании вектора: {e}")
        return []