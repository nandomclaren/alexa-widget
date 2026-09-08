"""Cliente HTTP para a lista de compras nativa da Alexa.

A Amazon descontinuou a List Skill API pública. Este cliente fala diretamente
com o endpoint interno (não documentado) que o próprio app/site da Alexa usa
para renderizar a lista de compras/tarefas, reaproveitando os cookies de sessão
obtidos via app/session_manager.py (alexapy).

Atenção: por ser engenharia reversa de um endpoint interno, a Amazon pode
alterar o formato de resposta ou o caminho a qualquer momento sem aviso. Se
isto parar de funcionar, veja o troubleshooting no README — normalmente basta
ajustar `amazon_todos_path`/`shopping_list_type` no .env ou os nomes de campo
em `_normalize_item` abaixo.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from .config import Settings
from .session_manager import AlexaSessionManager, SessionExpiredError

logger = logging.getLogger("alexa_widget.list_client")

__all__ = ["AmazonShoppingListClient", "AmazonListError", "SessionExpiredError"]


class AmazonListError(Exception):
    """A Amazon respondeu, mas de forma inesperada ou com erro."""


class AmazonShoppingListClient:
    def __init__(self, session_manager: AlexaSessionManager, settings: Settings) -> None:
        self._sessions = session_manager
        self._settings = settings

    @property
    def _base_url(self) -> str:
        return f"https://alexa.{self._settings.amazon_domain}"

    @property
    def _todos_url(self) -> str:
        return f"{self._base_url}{self._settings.amazon_todos_path}"

    @property
    def _timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=self._settings.request_timeout_seconds)

    async def _csrf_headers(self, login) -> dict[str, str]:
        await login.get_csrf()
        cookies = login.session.cookie_jar.filter_cookies(self._base_url)
        token = cookies.get("csrf")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["csrf"] = token.value
        return headers

    async def _raise_for_auth_errors(self, resp: aiohttp.ClientResponse) -> None:
        if resp.status in (401, 403):
            raise SessionExpiredError(
                "Amazon recusou a requisição (401/403): a sessão expirou ou o token CSRF é inválido."
            )
        content_type = resp.headers.get("Content-Type", "")
        if resp.status >= 400:
            body = await resp.text()
            logger.error("Amazon retornou %s para %s: %s", resp.status, resp.url, body[:500])
            raise AmazonListError(f"Amazon retornou erro {resp.status} ao acessar a lista de compras")
        if "application/json" not in content_type:
            # Normalmente significa que fomos redirecionados para uma página de
            # login/verificação HTML em vez de receber JSON: sessão inválida.
            body = await resp.text()
            logger.warning(
                "Resposta inesperada (Content-Type=%s) da Amazon; sessão provavelmente expirou: %s",
                content_type,
                body[:300],
            )
            raise SessionExpiredError(
                "A Amazon não retornou JSON (provável redirecionamento para login). "
                "A sessão expirou; reautentique pela interface web."
            )

    @staticmethod
    def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": raw.get("id") or raw.get("itemId"),
            "text": raw.get("text") or raw.get("value") or raw.get("name") or "",
            "completed": bool(raw.get("complete") or raw.get("completed") or False),
            "created_date": raw.get("createdDate") or raw.get("created") or raw.get("createdDateTime"),
        }

    async def _fetch_raw_items(self) -> list[dict[str, Any]]:
        login = await self._sessions.get_authenticated_login()
        params = {"type": self._settings.shopping_list_type, "size": "100"}
        async with login.session.get(self._todos_url, params=params, timeout=self._timeout) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)
        if isinstance(data, list):
            return data
        return data.get("values") or data.get("list") or []

    async def list_items(self) -> list[dict[str, Any]]:
        raw_items = await self._fetch_raw_items()
        return [self._normalize_item(item) for item in raw_items]

    async def add_item(self, text: str) -> dict[str, Any]:
        login = await self._sessions.get_authenticated_login()
        headers = await self._csrf_headers(login)
        payload = {"type": self._settings.shopping_list_type, "text": text, "complete": False}
        async with login.session.post(
            self._todos_url, json=payload, headers=headers, timeout=self._timeout
        ) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)
        return self._normalize_item(data)

    async def delete_item(self, item_id: str) -> None:
        login = await self._sessions.get_authenticated_login()
        headers = await self._csrf_headers(login)
        url = f"{self._todos_url}/{quote(str(item_id), safe='')}"
        params = {"type": self._settings.shopping_list_type}
        async with login.session.delete(
            url, params=params, headers=headers, timeout=self._timeout
        ) as resp:
            if resp.status == 404:
                raise AmazonListError(f"Item '{item_id}' não encontrado na lista")
            await self._raise_for_auth_errors(resp)

    async def complete_item(self, item_id: str) -> dict[str, Any]:
        raw_items = await self._fetch_raw_items()
        current = next((item for item in raw_items if str(item.get("id")) == str(item_id)), None)
        if current is None:
            raise AmazonListError(f"Item '{item_id}' não encontrado na lista")

        login = await self._sessions.get_authenticated_login()
        headers = await self._csrf_headers(login)
        url = f"{self._todos_url}/{quote(str(item_id), safe='')}"
        payload = {**current, "complete": True}
        async with login.session.put(
            url, json=payload, headers=headers, timeout=self._timeout
        ) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)
        return self._normalize_item(data)
