"""API route package."""
from fastapi import APIRouter

from app.api import auth, clients, connections, health

# Main router that combines all sub-routers
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(connections.router)
