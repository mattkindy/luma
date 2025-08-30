"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.endpoints import router

# Create FastAPI application
app = FastAPI(
    title="Luma Healthcare AI",
    description=(
        "A conversational AI service for healthcare appointment management "
        "with identity verification and session handling."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    tags_metadata=[
        {
            "name": "Conversation",
            "description": (
                "Handle conversational interactions with the AI assistant. "
                "Requires identity verification for appointment-related actions."
            ),
        },
        {
            "name": "Health",
            "description": "Service health monitoring and status checks.",
        },
    ],
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
