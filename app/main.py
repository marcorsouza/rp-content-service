import logging

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.jobs.races import run_races_job

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(
    title="Run Personal Content Service",
    version="0.1.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> str:
    if not api_key or api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key invalida.")
    return api_key


@app.get("/health", tags=["infra"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "run-personal-content-service",
        "environment": settings.app_env,
    }


@app.post("/jobs/races/run", tags=["jobs"], dependencies=[Depends(require_api_key)])
async def jobs_races_run(
    state: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Executa descoberta de corridas.
    - `state`: UF opcional (ex: SP, RJ). Se omitido, roda para todos os estados suportados.
    """
    result = await run_races_job(session, state=state)
    return result
