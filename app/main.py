from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import auth, chat, history, admin, contacts, upload

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(admin.router)
app.include_router(contacts.router)
app.include_router(upload.router)

@app.get("/")
async def root():
    return {"message": "Omni is alive!"}
