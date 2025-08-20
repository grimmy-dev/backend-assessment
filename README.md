# AI Content Generation System

🎥 **[Watch Demo Video](https://drive.google.com/file/d/17SQkdCyDHLHpVtNZUUNqYkMfmbFvzQSE/view?usp=drive_link)** | 📚 **[Full Documentation](PROJECT_DOCUMENTATION.md)**

---

## 🚀 Overview

**AI-powered FastAPI system** that transforms sales data into intelligent business insights through **concurrent AI processing**.

**v2.0 Features**: User management, 5x faster concurrent generation, dynamic CSV processing, Docker support.

Upload CSV → Get 5 AI business perspectives simultaneously in under 30 seconds.

---

## ✨ Key Features

- 👤 **User Management**: Multi-user data isolation
- ⚡ **Concurrent AI**: 5 agents run simultaneously (6-10s vs 30-50s)
- 🧠 **Smart CSV**: Auto-detects formats, encodings, separators
- 🗑️ **Data Cleanup**: Single-endpoint user data clearing
- 🐳 **Docker Ready**: Containerized deployment

### AI Agent Types

| Agent             | Focus                            | Processing |
| ----------------- | -------------------------------- | ---------- |
| Market Analyst    | Strategic analysis & positioning | Concurrent |
| Business Reporter | Stakeholder narratives           | Concurrent |
| Sales Strategist  | Actionable sales tactics         | Concurrent |
| Trend Forecaster  | Predictive insights              | Concurrent |
| Executive Briefer | C-level summaries                | Concurrent |

---

## ⚡ Quick Start

### Setup Options

**Local Install:**

```bash
git clone backend-assessment
cd backend-assessment
pip install -r requirements.txt
uvicorn main:app --reload
```

**Docker:**

#### 1. Build the Docker image

```bash
docker build -t backend-assignment .
```

#### 2. Run the container

```bash
docker run -it -p 8000:8000 \
  -e DATABASE_URL="your_database_url_here" \   # optional
  -e GOOGLE_AI_API_KEY="your_api_key_here" \  # required
  backend-assignment
```

- `-p 8000:8000` → Maps container port **8000** to host port **8000**
- `DATABASE_URL` → Optional, provide if using a database fallbacks to. in memeory storage
- `GOOGLE_AI_API_KEY` → Required, must be set for API access

---

### Configure Environment

```bash
# Create .env file
DATABASE_URL=postgresql://username:password@hostname/dbname
GOOGLE_AI_API_KEY=your_google_ai_key
```

### Usage

```bash
# Create user
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_user", "email": "demo@example.com"}'

# Upload data
curl -X POST "http://localhost:8000/upload-data" \
  -F "file=@data/sample_sales_data.csv"

# Generate articles (6-10 seconds)
time curl -X POST "http://localhost:8000/generate-articles"
```

### Access Points

- **Swagger UI** → http://localhost:8000/docs
- **Health Check** → http://localhost:8000/health
- **Stats Dashboard** → http://localhost:8000/stats

---

## 🏗️ Architecture

### Tech Stack

- **Backend**: FastAPI with async/await
- **Database**: PostgreSQL + In-memory fallback
- **AI**: Google AI API with concurrent processing
- **Processing**: Dynamic CSV parsing
- **Validation**: Pydantic models

### Database Schema

```sql
users → file_uploads → sales_data
users → articles

-- Foreign keys ensure data integrity
-- User scoping prevents data leakage
-- File tracking enables duplicate prevention
```

---

## 📊 Performance

| Feature            | v1.0   | v2.0         | Improvement               |
| ------------------ | ------ | ------------ | ------------------------- |
| Article Generation | 30-50s | 6-10s        | **5x faster**             |
| CSV Processing     | Basic  | Dynamic      | **90%+ formats**          |
| User Isolation     | None   | Complete     | **Multi-tenant**          |
| Data Relationships | Flat   | Foreign keys | **Referential integrity** |

---

## 🔧 API Endpoints

### User Management

```bash
# Create user
POST /users
{"username": "analyst1", "email": "analyst@company.com"}

# Get current user
GET /users/current

# Switch users
POST /users/{user_id}/set-current
```

### Data Operations

```bash
# Clear user data
DELETE /clear-data

# Enhanced stats
GET /stats
```

---

## 📁 Supported CSV Formats

Dynamic detection handles:

```csv
# Standard
date,product,sales_amount,quantity,region

# European (semicolon)
date;product;sales_amount;quantity;region

# Tab-separated
date	product	sales_amount	quantity	region

# Alternative columns (auto-mapped)
order_date,item,revenue,units,location
```

---

## 🧠 Business Intelligence

### Generated Insights

- Portfolio risk analysis
- Market positioning metrics
- Geographic performance
- Trend detection
- Data quality metrics

### Example Output

```json
{
  "insights": [
    "High-value transactions suggest premium positioning",
    "Diversified portfolio: top product 23.1% of sales",
    "Multi-region presence provides diversification"
  ]
}
```

---

## 📋 Requirements

- Python 3.12+
- PostgreSQL 12+ (optional)
- Google AI API key

### Dependencies

```txt
fastapi>=0.104.0
uvicorn>=0.24.0
asyncpg>=0.29.0
pandas>=2.1.0
pydantic>=2.5.0
python-multipart>=0.0.6
google-generativeai>=0.3.0
```

---

**Transform your sales data into actionable insights!** 🚀
