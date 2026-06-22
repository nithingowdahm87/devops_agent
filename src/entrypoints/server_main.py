import uvicorn
from src.config.settings import settings


def run_server(args):
    """Start the FastAPI server."""
    import uvicorn
    from src.api.main import app
    from src.config.settings import settings
    uvicorn.run(
        "src.api.main:app",
        host=settings.SERVER_HOST,
        port=args.port or settings.SERVER_PORT,
        reload=settings.ENVIRONMENT == "development",
    )
