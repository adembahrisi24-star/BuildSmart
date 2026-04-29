# 🏛️ BuildSmart — Architectural Design Platform

> Connecting clients with expert engineers for smarter, faster, and more beautiful architecture.

BuildSmart is a full-stack web platform built for the Tunisian market that bridges the gap between clients who have a vision and engineers who can bring it to life. From submitting a project to real-time collaboration and secure payment — everything happens in one place.

---

## ✨ What it does

- **Browse architectural styles** — explore a curated gallery of designs (Moderne, Minimaliste, Méditerranéen, and more)
- **Submit a project** — clients describe their vision, pick a style, choose an engineer, and set a budget
- **Real-time messaging** — instant direct messages between any two accounts, saved and persistent across sessions
- **Create an account** — register as a client or engineer, no external service needed
- **Engineer dashboard** — engineers manage incoming requests, track active projects, and monitor their revenue
- **Secure payments** — Escrow-based payment system that holds funds until delivery is confirmed

---

## 🛠️ Built with

| Layer | Technology |
|---|---|
| Backend | Python · Flask · Flask-SQLAlchemy · Flask-SocketIO |
| Database | SQLite (via SQLAlchemy ORM) |
| Real-time | WebSocket (Socket.IO) |
| Frontend | Vanilla HTML · CSS · JavaScript |
| Auth | Session-based with Werkzeug password hashing |

---

## 🚀 Getting started

**1. Clone the repo**
```bash
git clone https://github.com/adembahrisi24-star/BuildSmart.git
cd BuildSmart
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Run the app**
```bash
python app.py
```

**4. Open your browser**
```
http://localhost:5000
```

The database is created automatically on first run and seeded with demo data.

---

## 🔑 Demo accounts

| Role | Email | Password |
|---|---|---|
| Client | client@demo.com | 1234 |
| Engineer | ing@demo.com | 1234 |

Or just create your own account directly from the login page.

---

## 💬 Real-time chat

The messaging system is built on Socket.IO. Once logged in, any user can:

- Click **+ Nouveau** in the Messages tab to find and start a conversation with anyone
- Send messages that are delivered instantly to the other person
- Come back later and find the full conversation history right where they left it
- See who is online with a live green indicator

Messages are stored in the database — nothing is lost when you close the tab.

---

## 📁 Project structure

```
BuildSmart/
├── app.py              # All backend logic, routes, and Socket.IO events
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Single-page frontend
└── instance/
    └── buildsmart.db   # SQLite database (auto-generated)
```

---

## 🗺️ Roadmap

- [ ] File and plan attachments in chat
- [ ] Email notifications
- [ ] Mobile responsive layout
- [ ] Engineer profile pages
- [ ] Admin dashboard
- [ ] Stripe / Flouci payment integration

---

## 👤 Author

Made with ☕ and a lot of patience by **[@adembahrisi24-star](https://github.com/adembahrisi24-star)**

If you found this useful, drop a ⭐ on the repo — it genuinely means a lot.
