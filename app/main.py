"""Microserviço FastAPI que expõe a lista de compras nativa da Alexa como REST.

Veja o README.md para instruções de configuração, deploy e para o passo a
passo de extração manual de cookies via DevTools (usado como alternativa/
fallback ao login automático).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .amazon_list_client import AmazonListError, AmazonShoppingListClient
from .config import Settings, get_settings
from .models import AddItemRequest, LoginChallengeRequest, ShoppingItem
from .security import require_bearer_token
from .session_manager import AlexaSessionManager, SessionExpiredError

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("alexa_widget")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    session_manager = AlexaSessionManager(settings)
    app.state.session_manager = session_manager
    app.state.list_client = AmazonShoppingListClient(session_manager, settings)

    await session_manager.initialize()
    try:
        yield
    finally:
        await session_manager.shutdown()


app = FastAPI(
    title="Alexa Shopping List Bridge",
    description="Ponte não oficial entre a lista de compras da Alexa e uma API REST.",
    lifespan=lifespan,
)


def get_session_manager(request: Request) -> AlexaSessionManager:
    return request.app.state.session_manager


def get_list_client(request: Request) -> AmazonShoppingListClient:
    return request.app.state.list_client


@app.exception_handler(SessionExpiredError)
async def session_expired_handler(request: Request, exc: SessionExpiredError) -> JSONResponse:
    logger.warning("Sessão expirada: %s", exc)
    return JSONResponse(
        status_code=401,
        content={"error": "session_expired", "message": str(exc)},
    )


@app.exception_handler(AmazonListError)
async def amazon_list_error_handler(request: Request, exc: AmazonListError) -> JSONResponse:
    logger.error("Erro ao falar com a Amazon: %s", exc)
    return JSONResponse(
        status_code=502,
        content={"error": "amazon_error", "message": str(exc)},
    )


# ---------------------------------------------------------------------------
# Interface web mínima (botão de reautenticação + visualização da lista)
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def serve_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "auth.html")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health(
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    result = await session_manager.health_check()
    return {"status": "ok", "amazon_session": result}


# ---------------------------------------------------------------------------
# Autenticação / reautenticação
# ---------------------------------------------------------------------------

auth_router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_bearer_token)])


@auth_router.get("/status")
async def auth_status(
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    return session_manager.status_snapshot()


@auth_router.post("/login")
async def auth_login(
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Inicia (ou reinicia do zero) o login com a Amazon.

    É o endpoint que o botão "Reautenticar" da interface chama. Descarta
    qualquer sessão/cookies anteriores e começa um login novo com as
    credenciais do .env; a resposta indica se terminou (`authenticated`) ou
    se algum desafio (CAPTCHA, código OTP etc.) precisa ser respondido via
    POST /auth/challenge.
    """
    return await session_manager.start_login()


@auth_router.post("/challenge")
async def auth_challenge(
    payload: LoginChallengeRequest,
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo de desafio informado")
    return await session_manager.submit_challenge(data)


@auth_router.post("/continue")
async def auth_continue(
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Avança um fluxo de login que está apenas aguardando (ex.: aprovação de
    notificação no app Amazon), sem enviar nenhum dado novo."""
    return await session_manager.submit_challenge({})


app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Lista de compras
# ---------------------------------------------------------------------------

list_router = APIRouter(
    prefix="/api/lists/shopping", tags=["shopping-list"], dependencies=[Depends(require_bearer_token)]
)


@list_router.get("", response_model=list[ShoppingItem])
async def get_shopping_list(
    list_client: AmazonShoppingListClient = Depends(get_list_client),
) -> list[dict[str, Any]]:
    return await list_client.list_items()


@list_router.post("", response_model=ShoppingItem, status_code=201)
async def add_shopping_item(
    payload: AddItemRequest,
    list_client: AmazonShoppingListClient = Depends(get_list_client),
) -> dict[str, Any]:
    return await list_client.add_item(payload.text)


@list_router.delete("/{item_id}", status_code=204)
async def delete_shopping_item(
    item_id: str,
    list_client: AmazonShoppingListClient = Depends(get_list_client),
) -> None:
    await list_client.delete_item(item_id)


@list_router.post("/{item_id}/complete", response_model=ShoppingItem)
async def complete_shopping_item(
    item_id: str,
    list_client: AmazonShoppingListClient = Depends(get_list_client),
) -> dict[str, Any]:
    return await list_client.complete_item(item_id)


app.include_router(list_router)
