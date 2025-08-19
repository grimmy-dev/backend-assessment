# **AI Content Generation System**

## 🚀 Overview

An **AI-powered content generation system** built with **FastAPI**.  
It lets you **upload sales data (CSV)**, processes it, and generates **AI-driven business articles** with different perspectives for the day.

---

## ✨ Features

- **Health Check**: Verify system and storage status (`/health`).
- **Upload Sales Data**: Upload CSV files for ingestion (`/upload-data`).
- **Generate Articles**: Generate AI-based articles from sales data (`/generate-articles`).
- **Recent Articles**: Retrieve recent generated articles (`/articles/recent?days=7`).
- **System Stats**: Get data summary, recent articles count, and storage info (`/stats`).

---

## 🔌 Quick Start

### 1. Setup & Install

```bash
pip install -r requirements.txt
```

### 2. Run the App

```bash
uvicorn main:app --reload
```

### 3. Open API Docs

- Swagger UI → http://localhost:8000/docs
- ReDoc → http://localhost:8000/redoc

---

## ⚙️ Configuration

Environment variables (`.env`):

```bash
DATABASE_URL=postgresql://username:password@hostname/dbname   # Neon Cloud DB
GOOGLE_AI_API_KEY=your_google_ai_key
```

- Uses **Postgres on Neon** for persistence
- Falls back to **in-memory storage** if DB unavailable

---

## 📖 More Info

For detailed endpoint descriptions, sample outputs, and full documentation → see **`PROJECT_DOCUMENTATION.md`**.

---
