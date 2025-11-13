[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey)
![SQLModel](https://img.shields.io/badge/SQLModel-0.0.x-purple)
[![Deploy to Heroku](https://img.shields.io/badge/Deploy-Heroku-7056bf)](#deployment-heroku)

# PDI Timetracker – Flask Web App

A lightweight **time tracking system** built with Flask, SQLModel, and Jinja2 — including employee management and reporting.  

---

## 🚀 Features

- 🔐 **Login (MVP)** — simple authentication;
- 👥 **Employee management** — names, email, hire date, vacation days, gender, birth date
- ⏱️ **Time tracking** — start/end time, minutes conversion, manual entries
- 📊 **Reporting** — summaries and filters
- ☁️ **Heroku-ready deployment** with Postgres or SQLite

---

## 🧰 Tech Stack

- **Flask** (Backend, Routes, Templates)
- **SQLModel / SQLAlchemy** (Database ORM)
- **Pydantic** (Data validation)
- **SQLite** (local) / **PostgreSQL** (production)
- **Jinja2 + custom CSS**
  
---
<b>Login page</b>

<img width="1466" height="768" alt="Bildschirmfoto 2025-11-13 um 13 05 02" src="https://github.com/user-attachments/assets/184cbd27-2021-4c84-9026-d256d4b5c9a2" />

---
<b>Reporting page</b>

<img width="1466" height="768" alt="Bildschirmfoto 2025-11-13 um 13 04 15" src="https://github.com/user-attachments/assets/5274a655-87ee-4011-a5f0-aaa904f7ab54" />

---
<b>Time tracking page</b>

<img width="1466" height="768" alt="Bildschirmfoto 2025-11-13 um 13 20 21" src="https://github.com/user-attachments/assets/2119d9e0-08d8-415f-b995-34d3d5a92f1b" />

---

git clone https://github.com/7chrizz/pdi-timetracker.git

cd pdi-timetracker

python -m venv .venv

source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

flask --app flask_app:app run

---

Copyright (c) 2025 7chrizz


