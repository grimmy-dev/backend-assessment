from fastapi import FastAPI, UploadFile, File, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
from typing import List, Optional

from database.connection import Database
from services.data_ingestion import DataProcessor
from services.ai_agents import AIService
from config import settings
from lib.schemas import (
    UploadResponse,
    GenerationResponse,
    Article,
    User,
    CreateUserRequest,
)

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

# Simple global user ID storage
current_user_id: Optional[int] = None


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


@app.get("/health")
async def health_check():
    try:
        storage_info = await db.get_storage_info()
        return {"status": "healthy", "storage": storage_info, "version": "1.0.0"}
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "storage": {"type": "unknown", "connected": False},
            "version": "1.0.0",
        }


@app.post("/users", response_model=User)
async def create_user(user_request: CreateUserRequest = None):
    global current_user_id

    # Set defaults if no request body provided
    if user_request is None:
        import time

        timestamp = int(time.time())
        username = f"user_{timestamp}"
        email = f"{username}@example.com"
    else:
        username = user_request.username or f"user_{int(time.time())}"
        email = user_request.email or f"{username}@example.com"

    user = await db.create_user(username, email)
    if user:
        current_user_id = user.id
    return user


@app.get("/users/current", response_model=Optional[User])
async def get_current_user():
    if current_user_id:
        return await db.get_user(current_user_id)
    return None


@app.post("/users/{user_id}/set-current")
async def set_current_user(user_id: int):
    global current_user_id
    user = await db.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    current_user_id = user_id
    return {"message": f"Current user set to {user.username}"}


@app.post("/upload-data", response_model=UploadResponse)
async def upload_data(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV files are allowed"
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded"
            )
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await data_processor.process_csv(
            tmp_path, file.filename, current_user_id
        )
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
            upload_result = await data_processor.process_csv(
                tmp_path, file.filename, current_user_id
            )
            if upload_result.status == "error":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File processing failed",
                )
        finally:
            os.unlink(tmp_path)

    # Generate articles with concurrent processing
    result = await ai_service.generate_articles_with_check(current_user_id)

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

    articles = await db.get_recent_articles(days, current_user_id)
    return articles


@app.delete("/clear-data")
async def clear_data():
    """Clear all data for current user"""
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No current user set"
        )

    cleared_count = await db.clear_user_data(current_user_id)
    return {
        "status": "success",
        "message": f"Cleared all data for user {current_user_id}",
        "records_cleared": cleared_count,
    }


@app.get("/stats")
async def get_stats():
    summary = await db.get_enhanced_summary(current_user_id)
    articles = await db.get_recent_articles(30, current_user_id)
    storage_info = await db.get_storage_info()

    return {
        "status": "success",
        "current_user_id": current_user_id,
        "storage": storage_info,
        "data_summary": summary.model_dump(),
        "recent_articles_count": len(articles),
        "system_health": "optimal",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
