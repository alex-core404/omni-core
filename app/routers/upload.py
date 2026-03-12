from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import uuid
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
MAX_SIZE = 20 * 1024 * 1024

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (макс. 20 MB)")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"]:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат")

    filename = f"{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(contents)

    return {"url": f"/uploads/{filename}"}

    
