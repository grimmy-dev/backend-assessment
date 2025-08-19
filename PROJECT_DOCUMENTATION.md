# AI Content Generation System

## Overview

An **AI-powered content generation system** built with FastAPI that processes sales data and generates intelligent business articles through specialized AI agents.

**Key Value:** Transform raw sales data into actionable business insights through 5 different AI perspectives (Market Analyst, Business Reporter, Sales Strategist, Trend Forecaster, and Executive Briefer).

---

## Features

### Core Functionality

- 📊 **Data Processing**: Upload and validate CSV sales data with duplicate detection
- 🤖 **AI Article Generation**: Generate insights from 5 specialized AI agent perspectives
- 📈 **Analytics Dashboard**: View system stats, storage info, and performance metrics
- 📰 **Content Management**: Retrieve and manage generated articles
- 🔍 **Health Monitoring**: Real-time system health and database connectivity

### Technical Features

- Async/await support for high performance
- Automatic fallback from PostgreSQL to in-memory storage
- File hash-based duplicate upload prevention
- CORS enabled for frontend integration
- Comprehensive error handling and validation

---

## Quick Start

```bash
# 1. Clone and install
git clone backend-assessment
cd backend-assessment
pip install -r requirements.txt

# 2. Set environment variables
export DATABASE_URL="postgresql://username:password@hostname/dbname"
export GOOGLE_AI_API_KEY="your_google_ai_key"

# 3. Run the application
uvicorn main:app --reload

# 4. Open browser
# API Docs: http://localhost:8000/docs
# Health Check: http://localhost:8000/health
```

---

## Tech Stack

| Component      | Technology              | Purpose                              |
| -------------- | ----------------------- | ------------------------------------ |
| **Backend**    | FastAPI                 | High-performance async web framework |
| **Database**   | PostgreSQL (Neon Cloud) | Primary data storage                 |
| **Fallback**   | In-memory storage       | Backup when database unavailable     |
| **AI Service** | Google AI API           | Content generation                   |
| **Async DB**   | asyncpg                 | Non-blocking database operations     |
| **Validation** | Pydantic                | Data validation and serialization    |
| **Server**     | Uvicorn                 | ASGI server                          |

---

## Project Structure

```
project/
├── 📁 data/                    # Sample datasets
│   └── sample_sales_data.csv
├── 📁 database/                # Database layer
│   └── connection.py           # DB connection & queries
├── 📁 services/                # Business logic
│   ├── data_ingestion.py       # CSV processing & validation
│   └── ai_agents.py            # AI content generation
├── 📁 lib/                     # Data models
│   └── schemas.py              # Pydantic models
├── 📄 main.py                  # FastAPI app entry point
├── 📄 config.py                # Environment configuration
└── 📄 requirements.txt         # Python dependencies
```

---

## API Reference

### Base URL

```
http://localhost:8000
```

### Authentication

Currently no authentication required (add JWT/API keys for production).

---

### 1. Health Check

```http
GET /health
```

**Purpose:** System health monitoring and storage status

**Response:**

```json
{
  "status": "healthy",
  "storage": {
    "type": "database", // or "memory"
    "connected": true,
    "file_count": 0
  },
  "version": "1.0.0"
}
```

---

### 2. Upload Sales Data

```http
POST /upload-data
Content-Type: multipart/form-data
```

**Purpose:** Upload and process CSV sales data with validation

**Parameters:**

- `file` (required): CSV file with sales data

**CSV Format Expected:**

```csv
date,product,region,sales_amount,quantity
2024-01-01,Product A,North,1000.50,10
2024-01-02,Product B,South,750.25,5
```

**Success Response (200):**

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
        "product": "Product A",
        "total_sales": 450000.0
      }
    ],
    "unique_products": 5,
    "unique_regions": 3,
    "date_range": {
      "start": "2024-01-01",
      "end": "2024-02-29"
    }
  },
  "insights": [
    "Date column successfully parsed and standardized",
    "Processed 60 sales transactions",
    "Total revenue: $927,422.50"
  ],
  "file_hash": "3caa70557c2d...",
  "duplicate_upload": false
}
```

**Error Responses:**

- `400`: Invalid file format, empty file, or processing error
- `422`: Missing file parameter

---

### 3. Generate Articles

```http
POST /generate-articles
```

**Purpose:** Generate AI-powered articles from uploaded sales data using 5 specialized agents

**Optional Parameters:**

- `file` (multipart/form-data): Upload CSV and generate articles in one step

**Success Response (200):**

```json
{
  "status": "success",
  "articles_generated": 5,
  "articles": [
    {
      "id": 1,
      "title": "Market Analyst Report - August 2025",
      "article_type": "market_analyst",
      "content": "Comprehensive market analysis showing...",
      "generated_date": "2025-08-19"
    },
    {
      "id": 2,
      "title": "Business Reporter Report - August 2025",
      "article_type": "business_reporter",
      "content": "## Quarterly Performance Overview...",
      "generated_date": "2025-08-19"
    }
    // ... 3 more articles
  ],
  "data_summary": {
    "total_sales": 927422.5,
    "record_count": 60
  }
}
```

**Error Response:**

- `400`: No data available for article generation

#### AI Agent Types:

- **Market Analyst**: Technical analysis and market trends
- **Business Reporter**: Investor-focused reporting and insights
- **Sales Strategist**: Action plans and sales recommendations
- **Trend Forecaster**: Future predictions and forecasting
- **Executive Briefer**: C-level summaries and strategic overview

---

### 4. Recent Articles

```http
GET /articles/recent?days=7
```

**Purpose:** Retrieve recently generated articles

**Query Parameters:**

- `days` (optional): Number of days to look back (default: 7, range: 1-365)

**Response (200):**

```json
[
  {
    "id": 5,
    "title": "Executive Briefer Report - August 2025",
    "article_type": "executive_briefer",
    "content": "## CEO Update...",
    "generated_date": "2025-08-19"
  }
]
```

**Error Response:**

- `400`: Invalid days parameter (must be 1-365)

---

### 5. System Statistics

```http
GET /stats
```

**Purpose:** Comprehensive system overview and performance metrics

**Response (200):**

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
    "unique_products": 5,
    "unique_regions": 3,
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

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@hostname:port/database
# Example: postgresql://user:pass@ep-cool-lab-123456.us-east-2.aws.neon.tech/neondb

# AI Service Configuration
GOOGLE_AI_API_KEY=your_google_ai_api_key_here

# Optional: Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=True
```

### Database Setup

The system automatically handles database connectivity:

1. **Primary**: PostgreSQL (Neon Cloud Database)
2. **Fallback**: In-memory storage (if database unavailable)
3. **Auto-detection**: System detects and switches storage types automatically

---

## Manual Testing

### API Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Upload sample data
curl -X POST "http://localhost:8000/upload-data" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/sample_sales_data.csv"

# Generate articles
curl -X POST "http://localhost:8000/generate-articles"

# Get recent articles
curl "http://localhost:8000/articles/recent?days=7"

# Check system stats
curl http://localhost:8000/stats
```

---

## Deployment

### Local Development

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Environment-Specific Notes

- **Development**: Enable `--reload` for auto-restart on file changes

---

## Error Handling

The system provides comprehensive error responses:

| Status Code | Description           | Common Causes                                      |
| ----------- | --------------------- | -------------------------------------------------- |
| `200`       | Success               | Request completed successfully                     |
| `400`       | Bad Request           | Invalid file format, empty file, processing errors |
| `422`       | Unprocessable Entity  | Missing required parameters, validation errors     |
| `500`       | Internal Server Error | Database connectivity issues, AI service errors    |

### Error Response Format

```json
{
  "detail": "Descriptive error message",
  "status_code": 400
}
```

---

## Performance & Limits

- **File Upload**: Max 10MB CSV files
- **Concurrent Requests**: Supports async processing
- **Article Generation**: ~30-60 seconds for 5 articles
- **Database**: Auto-fallback to in-memory if PostgreSQL unavailable
- **Rate Limiting**: Consider adding for production use

---

## Security Considerations

### Current State (Development)

- No authentication required
- CORS enabled for all origins
- Basic file validation

---

## Troubleshooting

### Common Issues

**Database Connection Failed**

```bash
# Check environment variable
echo $DATABASE_URL

# Test connection manually
psql $DATABASE_URL -c "SELECT 1;"
```

**AI Article Generation Fails**

```bash
# Verify API key
echo $GOOGLE_AI_API_KEY

# Check if data exists
curl http://localhost:8000/stats
```

**File Upload Issues**

- Ensure CSV has proper headers
- Check file size (< 10MB)
- Verify file encoding (UTF-8)

### Debug Mode

```bash
# Enable detailed logging
uvicorn main:app --reload --log-level debug
```

---

- For Best outcomes make sure the dataset follows the types same as `sample_sales_data.csv` in `/data`
