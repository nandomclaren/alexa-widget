"""Autenticação simples por Bearer token para proteger a API."""

import hmac

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings


async def require_bearer_token(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, settings.bearer_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso ausente ou inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
