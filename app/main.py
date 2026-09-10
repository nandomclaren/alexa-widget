"""Microserviço FastAPI que expõe a lista de compras nativa da Alexa como REST.

Veja o README.md para instruções de configuração, deploy e para o passo a
passo de extração manual de cookies via DevTools (usado como alternativa/
fallback ao login automático).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

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
    deep: bool = False,
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Por padrão não bate na Amazon (seguro para o healthcheck automático do
    Docker/Railway rodar a cada poucos segundos). Passe ?deep=true para forçar
    uma verificação real da sessão com a Amazon."""
    result = await session_manager.health_check(deep=deep)
    return {"status": "ok", "amazon_session": result}


@app.get("/debug/last-login-page", include_in_schema=False)
async def debug_last_login_page(
    request: Request,
    kind: str = "post",
    token: Optional[str] = None,
    settings_dep: Settings = Depends(get_settings),
) -> HTMLResponse:
    """Mostra o HTML bruto que a Amazon devolveu no último GET/POST do login.

    Só funciona com LOGIN_DEBUG=true (é aí que a alexapy grava esses arquivos).
    Aceita o token via query string (?token=...) além do header, só para poder
    abrir direto no navegador durante depuração — não use isso para nada além
    disso.
    """
    if not settings_dep.login_debug:
        raise HTTPException(status_code=404, detail="LOGIN_DEBUG está desativado; ative no .env/variáveis e reinicie")

    auth_header = request.headers.get("authorization", "")
    _, _, header_token = auth_header.partition(" ")
    provided = token or header_token
    if not provided or not hmac.compare_digest(provided, settings_dep.bearer_token):
        raise HTTPException(status_code=401, detail="Token ausente ou inválido (use ?token=... ou o header)")

    if kind not in ("get", "post"):
        raise HTTPException(status_code=400, detail="kind deve ser 'get' ou 'post'")

    filename = f"alexa_media{settings_dep.amazon_email}{kind}.html"
    path = os.path.join(settings_dep.data_dir, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Arquivo ainda não existe: {filename}. Tente reautenticar primeiro.")

    with open(path, "rb") as f:
        content = f.read()
    return HTMLResponse(content=content)


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


@auth_router.post("/upload-cookies")
async def upload_cookies(request: Request, settings_dep: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Recebe o conteúdo do arquivo de cookies gerado por um login feito de
    outra rede (ex.: em casa, onde a Amazon não bloqueia por IP de
    datacenter) e grava no volume, no caminho exato que a alexapy usa para
    persistir sessão. Depois de enviar, chame POST /auth/resume-from-cookies
    para a sessão em execução carregar esse arquivo.

    O corpo da requisição deve ser exatamente o conteúdo do arquivo
    `<DATA_DIR>/.storage/alexa_media<AMAZON_EMAIL>.cookies` gerado localmente.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Corpo da requisição vazio")
    try:
        json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Conteúdo não é um JSON válido: {exc}") from exc

    filename = f".storage/alexa_media.{settings_dep.amazon_email}.cookies"
    path = os.path.join(settings_dep.data_dir, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(body)
    return {"status": "ok", "path": filename}


@auth_router.post("/resume-from-cookies")
async def resume_from_cookies(
    session_manager: AlexaSessionManager = Depends(get_session_manager),
) -> dict[str, Any]:
    """Recarrega os cookies salvos em disco (ver /auth/upload-cookies) e
    tenta retomar a sessão com eles, sem passar pelo login por credenciais."""
    return await session_manager.resume_from_saved_cookies()


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
