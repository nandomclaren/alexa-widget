"""Cliente HTTP para a lista de compras padrão da Alexa.

A lista que a Alexa alimenta por voz ("Alexa, adicione leite à lista de
compras") é gerenciada por uma API JSON dedicada da Amazon,
`/alexashoppinglists/api/...`, no mesmo domínio do site de varejo (ex.:
www.amazon.fr). Isto NÃO é o sistema de Listas/Wish List comum do site
(`/hz/wishlist/...` — serve pra listas de desejos criadas manualmente, não
pra lista de compras por voz) nem o antigo painel web da Alexa
(alexa.amazon.<domínio>) com seu endpoint /api/todos — ambos descontinuados
pela Amazon. Reverso-engenheirado via DevTools; veja o README para como
reidentificar os endpoints caso a Amazon mude de novo.
"""

from __future__ import annotations

import logging
from typing import Any

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
        return f"https://www.{self._settings.amazon_domain}/alexashoppinglists/api"

    @property
    def _list_id(self) -> str:
        return self._settings.amazon_shopping_list_id

    @property
    def _timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=self._settings.request_timeout_seconds)

    async def _raise_for_auth_errors(self, resp: aiohttp.ClientResponse) -> None:
        if resp.status in (401, 403):
            raise SessionExpiredError(
                "Amazon recusou a requisição (401/403): a sessão expirou ou é inválida."
            )
        if resp.status >= 400:
            body = await resp.text()
            logger.error("Amazon retornou %s para %s: %s", resp.status, resp.url, body[:500])
            raise AmazonListError(f"Amazon retornou erro {resp.status} ao acessar a lista de compras")

    @staticmethod
    def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": raw.get("id"),
            "text": raw.get("value") or "",
            "completed": bool(raw.get("completed", False)),
            "created_date": raw.get("createdDateTime"),
        }

    async def _fetch_raw_items(self, login) -> list[dict[str, Any]]:
        url = f"{self._base_url}/getlistitems"
        async with login.session.get(url, timeout=self._timeout) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)

        list_data = data.get(self._list_id)
        if list_data is None:
            # A Amazon pode variar a chave em algumas contas; se só existir
            # uma lista na resposta, assume que é a nossa.
            if len(data) == 1:
                list_data = next(iter(data.values()))
            else:
                raise AmazonListError(f"Lista '{self._list_id}' não encontrada na resposta da Amazon")
        return list_data.get("listItems", [])

    async def _get_raw_item(self, login, item_id: str) -> dict[str, Any]:
        items = await self._fetch_raw_items(login)
        match = next((item for item in items if item.get("id") == item_id), None)
        if match is None:
            raise AmazonListError(f"Item '{item_id}' não encontrado na lista")
        return match

    async def list_items(self) -> list[dict[str, Any]]:
        login = await self._sessions.get_authenticated_login()
        raw_items = await self._fetch_raw_items(login)
        return [self._normalize_item(item) for item in raw_items]

    async def add_item(self, text: str) -> dict[str, Any]:
        login = await self._sessions.get_authenticated_login()
        url = f"{self._base_url}/addlistitem/{self._list_id}"
        payload = {"value": text, "listItemMetadata": []}
        async with login.session.post(url, json=payload, timeout=self._timeout) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)
        return self._normalize_item(data)

    async def complete_item(self, item_id: str) -> dict[str, Any]:
        login = await self._sessions.get_authenticated_login()
        raw = await self._get_raw_item(login, item_id)
        payload = {**raw, "completed": True}
        url = f"{self._base_url}/updatelistitem"
        async with login.session.post(url, json=payload, timeout=self._timeout) as resp:
            await self._raise_for_auth_errors(resp)
            data = await resp.json(content_type=None)
        return self._normalize_item(data)

    async def delete_item(self, item_id: str) -> None:
        login = await self._sessions.get_authenticated_login()
        raw = await self._get_raw_item(login, item_id)
        url = f"{self._base_url}/deletelistitem"
        async with login.session.post(url, json=raw, timeout=self._timeout) as resp:
            await self._raise_for_auth_errors(resp)
