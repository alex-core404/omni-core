from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

async def get_embedding(text: str) -> list[float]:
    try:
        clean_text = text.replace("\n", " ").strip()
        embedding = model.encode(clean_text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        print(f"Ошибка при создании вектора: {e}")
        return []