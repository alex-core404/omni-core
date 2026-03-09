from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import auth, chat, history

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(history.router)

@app.get("/")
async def root():
    return {"message": "Omni is alive!"}
