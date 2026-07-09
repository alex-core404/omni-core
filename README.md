# 🤖 Omni — Encrypted AI Messenger

Real-time messenger with AI assistant and end-to-end message encryption.

![Omni Chat](screenshots/chat.png)

## ✨ Features

- 💬 **Real-time chat** via WebSocket
- 🔐 **AES-256 encryption** for all messages (CFB mode)
- 🤖 **AI assistant** — personal chat with Omni AI (Gemini)
- ✅ **Read receipts** (✓ / ✓✓)
- ↩️ **Reply/quotes** like Telegram
- 😂 **Reactions** on messages (6 emoji, long press)
- 📎 **Photo upload** with lightbox viewer
- 📝 **Markdown + syntax highlighting** (highlight.js)
- 🟢 **Online status** indicators in real time
- 🔔 **Unread counter** in browser tab
- 👤 **Profile** with username setup
- 📱 **Responsive design** for mobile

## 🛠 Tech Stack

**Backend:** Python 3.10, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis

**Security:** AES-256 CFB, JWT

**AI:** OpenRouter API, Gemini

**Frontend:** Vanilla JS, HTML/CSS, marked.js, highlight.js

**Infrastructure:** Ubuntu 22.04, systemd

## 🚀 Getting Started

**Requirements:** Python 3.10+, PostgreSQL, Redis

```bash
git clone https://github.com/alex-core404/omni-core.git
cd omni-core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.env` file:

```env
DATABASE_URL=postgresql://omni_user:password@localhost/omni_db
SECRET_KEY=your_secret_key
ADMIN_KEY=your_admin_key
OPENROUTER_API_KEY=your_openrouter_key
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ALGORITHM=HS256
```

Run migrations and start:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📁 Project Structure
omni-core/
├── app/
│   ├── main.py          # Entry point
│   ├── database.py      # DB connection
│   ├── crypto.py        # AES-256 encryption
│   ├── models/          # SQLAlchemy models
│   ├── routers/         # API endpoints
│   ├── utils/           # Utilities
│   └── static/          # Frontend (HTML/CSS/JS)
├── migrations/          # Alembic migrations
├── scripts/             # Helper scripts
└── requirements.txt

## 🗺 Roadmap

- [x] JWT authentication
- [x] WebSocket + Redis
- [x] AES-256 encryption
- [x] Photo upload + lightbox
- [x] Read receipts
- [x] Message reactions
- [x] Reply/quotes
- [x] AI integration
- [ ] Docker Compose
- [ ] CI/CD (GitHub Actions)
- [ ] HTTPS + custom domain

## 👨‍💻 Author

**Aleksandr Sotnikov** — [GitHub](https://github.com/alex-core404)
