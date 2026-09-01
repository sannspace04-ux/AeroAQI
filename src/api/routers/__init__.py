# src/api/routers/__init__.py
# Re-export all router modules so main.py can import them cleanly.
from src.api.routers import fire, health, observations, pipeline, stations, weather

__all__ = ["fire", "health", "observations", "pipeline", "stations", "weather"]
