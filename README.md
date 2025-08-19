# AI Content Generation System

🎥 **[Watch Demo Video](https://drive.google.com/file/d/17SQkdCyDHLHpVtNZUUNqYkMfmbFvzQSE/view?usp=drive_link)** | 📚 **[Full Documentation](PROJECT_DOCUMENTATION.md)**

---

## 🚀 Overview

An **AI-powered content generation system** built with **FastAPI** that transforms sales data into intelligent business insights.

Upload CSV sales data → Get 5 different AI-generated business articles (Market Analyst, Business Reporter, Sales Strategist, Trend Forecaster, Executive Briefer).

---

## ✨ Features

- 📊 **Upload Sales Data**: CSV file processing with validation (`/upload-data`)
- 🤖 **AI Article Generation**: 5 specialized AI agents create unique perspectives (`/generate-articles`)
- 📰 **Content Management**: Retrieve recent articles (`/articles/recent`)
- 📈 **System Analytics**: Data summaries and performance stats (`/stats`)
- 🔍 **Health Monitoring**: Real-time system status (`/health`)

---

## ⚡ Quick Start

### 1. Setup & Install
```bash
git clone backend-assessment
cd backend-assessment
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Create .env file
DATABASE_URL=postgresql://username:password@hostname/dbname
GOOGLE_AI_API_KEY=your_google_ai_key
```

### 3. Run the Application
```bash
uvicorn main:app --reload
```

### 4. Access API
- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc
- **Health Check** → http://localhost:8000/health

---

## 🏗️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL (Neon Cloud) + In-memory fallback
- **AI**: Google AI API
- **Async**: asyncpg for non-blocking DB operations

---

## 📝 Usage Example

```bash
# 1. Upload your sales data
curl -X POST "http://localhost:8000/upload-data" \
  -F "file=@your_sales_data.csv"

# 2. Generate AI articles
curl -X POST "http://localhost:8000/generate-articles"

# 3. View results
curl "http://localhost:8000/articles/recent"
```

---

## 📚 Documentation

For detailed API reference, sample responses, deployment guides, and troubleshooting:

➡️ **[Complete Documentation](PROJECT_DOCUMENTATION.md)**

---

## 🚀 What's Next?

- Authentication & user management
- Frontend dashboard
- More AI agent types
- Real-time notifications
- Export to PDF/Word

---
