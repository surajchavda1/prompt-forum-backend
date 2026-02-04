import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from pathlib import Path

from app.database import Database
from app.routes.auth.auth_routes import router as auth_router
from app.routes.auth.profile_routes import router as profile_router
from app.routes.forum.category_routes import router as category_router
from app.routes.forum.tag_routes import router as tag_router
from app.routes.forum.post_routes import router as post_router
from app.routes.forum.comment_routes import router as comment_router
from app.routes.files.upload_routes import router as upload_router
from app.routes.contest.contest_routes import router as contest_router
from app.routes.contest.task_routes import router as task_router
from app.routes.contest.submission_routes import contest_router as contest_submission_router, submission_router
from app.routes.contest.leaderboard_routes import router as leaderboard_router
from app.routes.contest.user_contests_routes import router as user_contests_router
from app.routes.search.search_routes import router as search_router
from app.routes.payment.wallet_routes import router as wallet_router
from app.routes.payment.payment_routes import router as payment_router
from app.routes.payment.webhook_routes import router as webhook_router
from app.routes.payment.withdrawal_routes import router as withdrawal_router

# Load environment variables
load_dotenv()

# Get environment variables
APP_NAME = os.getenv("APP_NAME", "PromptForum")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the application"""
    # Startup
    await Database.connect_db()
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    yield
    # Shutdown
    await Database.close_db()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="PromptForum API with Authentication, Categories, Tags, Posts, and Comments",
    lifespan=lifespan
)

# CORS middleware
# In development, allow all origins for easier testing
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

cors_origins = [
    FRONTEND_URL, 
    "http://localhost:3000", 
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if not DEBUG else ["*"],
    allow_credentials=not DEBUG,  # Can't use credentials with wildcard origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(profile_router)  # Profile routes already have /api prefix
app.include_router(category_router, prefix="/api")
app.include_router(tag_router, prefix="/api")
app.include_router(post_router, prefix="/api")
app.include_router(comment_router, prefix="/api")
app.include_router(upload_router, prefix="/api")
app.include_router(contest_router, prefix="/api")
app.include_router(task_router, prefix="/api")
app.include_router(contest_submission_router, prefix="/api")  # Contest-specific submission routes
app.include_router(submission_router, prefix="/api")  # Generic submission operations
app.include_router(leaderboard_router, prefix="/api")
app.include_router(user_contests_router)  # User contest routes (already has /api prefix)
app.include_router(search_router, prefix="/api")  # Global search
app.include_router(wallet_router, prefix="/api")  # Wallet operations
app.include_router(payment_router, prefix="/api")  # Payment operations
app.include_router(webhook_router, prefix="/api")  # Payment webhooks
app.include_router(withdrawal_router, prefix="/api")  # Withdrawal operations

# Mount uploads directory for static file serving
uploads_path = Path("uploads")
if uploads_path.exists():
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
async def read_root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {APP_NAME} API",
        "version": APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/test-payment")
async def test_payment_page():
    """Serve test payment HTML page"""
    from fastapi.responses import FileResponse
    return FileResponse("test_payment.html", media_type="text/html")