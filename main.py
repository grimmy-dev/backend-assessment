from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
from typing import List

from database.connection import Database
from services.data_ingestion import DataProcessor
from services.ai_agents import AIService
from config import settings
from lib.schemas import UploadResponse, GenerationResponse, Article

app = FastAPI(title="AI Content Generation System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
db = Database(settings.database_url)
data_processor = DataProcessor(db)
ai_service = AIService(db)


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.get("/health")
async def health_check():
    storage_info = await db.get_storage_info()
    return {"status": "healthy", "storage": storage_info, "version": "1.0.0"}


@app.post("/upload-data", response_model=UploadResponse)
async def upload_data(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are allowed"
        )

    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded"
            )
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await data_processor.process_csv(tmp_path)
        return result
    finally:
        os.unlink(tmp_path)


@app.post("/generate-articles", response_model=GenerationResponse)
async def generate_articles(file: UploadFile = File(None)):
    # Process file if provided
    if file:
        if not file.filename or not file.filename.endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are allowed",
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            content = await file.read()
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty file uploaded",
                )
            tmp.write(content)
            tmp_path = tmp.name

        try:
            upload_result = await data_processor.process_csv(tmp_path)
            if upload_result.status == "error":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File processing failed",
                )
        finally:
            os.unlink(tmp_path)

    # Generate articles with built-in data checking
    result = await ai_service.generate_articles_with_check()

    if result.status == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data available for article generation. Please upload data first.",
        )

    return result


@app.get("/articles/recent", response_model=List[Article])
async def get_recent_articles(days: int = 7):
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Days must be between 1 and 365",
        )

    articles = await db.get_recent_articles(days)
    return articles


@app.get("/stats")
async def get_stats():
    summary = await db.get_enhanced_summary()
    articles = await db.get_recent_articles(30)
    storage_info = await db.get_storage_info()

    return {
        "status": "success",
        "storage": storage_info,
        "data_summary": summary.model_dump(),
        "recent_articles_count": len(articles),
        "system_health": "optimal",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
