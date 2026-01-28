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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
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