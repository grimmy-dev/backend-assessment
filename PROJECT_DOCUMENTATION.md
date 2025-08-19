# **AI Content Generation System**

## **Overview**

This project is an **AI-powered content generation system** built with **FastAPI**.  
It allows uploading sales data (CSV), processes the data, and generates AI-driven articles based on insights for the day.

---

## **Features**

- **Health Check**: Verify system and storage status (`/health`).
- **Upload Sales Data**: Upload CSV files for ingestion (`/upload-data`).
- **Generate Articles**: Generate AI-based articles from sales data (`/generate-articles`).
- **Recent Articles**: Retrieve recent generated articles (`/articles/recent?days=7`).
- **System Stats**: Get data summary, recent articles count, and storage info (`/stats`).

---

## **Tech Stack**

- **FastAPI** (backend framework)
- **PostgreSQL (Neon Cloud Database) / In-memory storage** (data persistence)
- **asyncpg** (async database connection)
- **Pydantic & pydantic-settings** (validation & config)
- **Google AI API** (for AI article generation)
- **Uvicorn** (ASGI server)

---

## **Project Structure**

```
project/
│── data/                  # Sample dataset
│   └── sample_sales_data.csv
│── database/              # Database connection & queries
│   └── connection.py
│── lib/                   # Schemas & models
│   └── schemas.py
│── services/              # Business logic & AI services
│   ├── data_ingestion.py
│   └── ai_agents.py
│── main.py                # FastAPI application entrypoint
│── config.py              # Configuration (env variables)
│── test_api.py            # API test script
│── requirements.txt       # Dependencies
│── PROJECT_DOCUMENTATION.md
```

---

## **API Endpoints**

### **1. Health Check**

```http
GET /health
```

**Description:** Returns system health and storage info.

**Sample Output:**

```json
{
  "status": "healthy",
  "storage": {
    "type": "database",
    "connected": true,
    "file_count": 0
  },
  "version": "1.0.0"
}
```

---

### **2. Upload Sales Data**

```http
POST /upload-data
```

**Description:**

- Accepts **CSV file**
- Validates, processes, and stores sales data
- Prevents duplicate uploads using file hash

**Sample Output:**

```json
{
  "status": "success",
  "rows_processed": 60,
  "rows_stored": 60,
  "summary": {
    "total_sales": 927422.5,
    "average_sales": 15457.04,
    "record_count": 60,
    "top_products": [
      {
        "product": "Unknown",
        "total_sales": 927422.5
      }
    ],
    "unique_products": 1,
    "unique_regions": 1,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-02-29"
    }
  },
  "insights": [
    "Date column successfully parsed and standardized",
    "Processed 60 sales transactions",
    "Total revenue: $927,422.50",
    "Average transaction: $15457.04",
    "Top product 'Unknown' contributes 100.0% of total sales"
  ],
  "file_hash": "3caa70557....",
  "duplicate_upload": false
}
```

---

### **3. Generate Articles**

```http
POST /generate-articles
```

**Description:**

- Uses uploaded sales data
- Calls AI service to generate articles across **5 agent types**

**Sample Output (showing all 5 article agents with content):**

```json
{
  "status": "success",
  "articles_generated": 5,
  "articles": [
    {
      "id": 1,
      "title": "Market Analyst Report - August 2025",
      "article_type": "market_analyst",
      "content": "The client's Q1 performance... [detailed analysis]",
      "generated_date": "2025-08-19"
    },
    {
      "id": 2,
      "title": "Business Reporter Report - August 2025",
      "article_type": "business_reporter",
      "content": "## One-Trick Pony Rides High... [investor-oriented reporting]",
      "generated_date": "2025-08-19"
    },
    {
      "id": 3,
      "title": "Sales Strategist Report - August 2025",
      "article_type": "sales_strategist",
      "content": "Alright team, let's turn this data into dollars... [action plan]",
      "generated_date": "2025-08-19"
    },
    {
      "id": 4,
      "title": "Trend Forecaster Report - August 2025",
      "article_type": "trend_forecaster",
      "content": "Analyzing the provided data, a clear picture emerges... [future outlook]",
      "generated_date": "2025-08-19"
    },
    {
      "id": 5,
      "title": "Executive Briefer Report - August 2025",
      "article_type": "executive_briefer",
      "content": "## CEO Update: February Performance Review... [leadership summary]",
      "generated_date": "2025-08-19"
    }
  ],
  "data_summary": {
    "total_sales": 927422.5,
    "average_sales": 15457.04,
    "record_count": 60,
    "unique_products": 1,
    "unique_regions": 1
  }
}
```

---

### **4. Recent Articles**

```http
GET /articles/recent?days=7
```

**Description:** Returns articles generated in the past given days (default: 7).

**Sample Output:**

```json
[
  {
    "id": 5,
    "title": "Executive Briefer Report - August 2025",
    "article_type": "executive_briefer",
    "generated_date": "2025-08-19"
  },
  {
    "id": 4,
    "title": "Trend Forecaster Report - August 2025",
    "article_type": "trend_forecaster",
    "generated_date": "2025-08-19"
  }
]
```

---

### **5. System Stats**

```http
GET /stats
```

**Description:** Provides system summary (sales data, articles count, DB status).

**Sample Output:**

```json
{
  "status": "success",
  "storage": {
    "type": "database",
    "connected": true,
    "file_count": 1
  },
  "data_summary": {
    "total_sales": 927422.5,
    "average_sales": 15457.04,
    "record_count": 60,
    "unique_products": 1,
    "unique_regions": 1,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-02-29"
    }
  },
  "recent_articles_count": 5,
  "system_health": "optimal"
}
```

---

## **Configuration**

This project uses **Postgres hosted on Neon (cloud database)** for persistent storage.  
If the Neon connection is not available, the system gracefully **falls back to in-memory storage**.

Environment variables (`.env`):

```
DATABASE_URL=postgresql://username:password@hostname/dbname
GOOGLE_AI_API_KEY=your_google_ai_key
```

---

## **Running the Project**

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run FastAPI app:

```bash
uvicorn main:app --reload
```

3. API Docs:

- Swagger → http://localhost:8000/docs
- ReDoc → http://localhost:8000/redoc

---

## **Notes**

- If Neon Postgres is unavailable, falls back to in-memory mode.
- Articles are only generated **after data upload** (or by uploading file directly in `/generate-articles`).
- For best testing results, match dataset structure with `sample_sales_data.csv`.

---
