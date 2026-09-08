"""Gerencia o ciclo de vida da sessão web autenticada com a Amazon.

Usa a biblioteca `alexapy` (mesma base do Home Assistant) apenas para a parte
difícil de manter: login, CAPTCHA/OTP, refresh e persistência de cookies. A
manipulação da lista de compras em si é feita à parte, em amazon_list_client.py,
reaproveitando a sessão HTTP autenticada que este módulo expõe.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from alexapy import AlexaLogin

from .config import Settings

logger = logging.getLogger("alexa_widget.session")

# Flags de status da alexapy que exigem uma resposta do usuário para continuar
# o login (ver alexapy.alexalogin.AlexaLogin._process_page).
_CHALLENGE_FLAGS = (
    "captcha_required",
    "securitycode_required",
    "verificationcode_required",
    "claimspicker_required",
    "authselect_required",
)

# Máximo de passos "mecânicos" (redirects/polling) que avançamos sozinhos
# entre uma chamada do usuário e a próxima, antes de devolver o controle.
_MAX_AUTO_STEPS = 4


class SessionExpiredError(Exception):
    """A sessão da Amazon não está (mais) autenticada."""


class AlexaSessionManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._login: AlexaLogin | None = None
        self._last_health_check: float = 0.0
        self._last_health_ok: bool = False

    # -- ciclo de vida -----------------------------------------------------

    async def initialize(self) -> None:
        """Chamado na inicialização: tenta retomar uma sessão salva em disco."""
        async with self._lock:
            self._login = self._new_login()
            try:
                cookies = await self._login.load_cookie()
                await self._login.login(cookies=cookies or {})
            except Exception:
                logger.exception("Falha inesperada ao tentar retomar a sessão salva da Amazon")

        if self.is_authenticated:
            logger.info("Sessão da Amazon retomada com sucesso a partir dos cookies salvos.")
        else:
            logger.warning(
                "Nenhuma sessão válida da Amazon foi encontrada em %s. "
                "Abra a interface web e clique em 'Reautenticar' (ou chame POST /auth/login) "
                "para iniciar o login.",
                self._settings.data_dir,
            )

    async def shutdown(self) -> None:
        if self._login:
            await self._login.close()

    def _new_login(self) -> AlexaLogin:
        return AlexaLogin(
            url=self._settings.amazon_domain,
            email=self._settings.amazon_email,
            password=self._settings.amazon_password,
            outputpath=self._outputpath,
            debug=self._settings.login_debug,
            otp_secret=self._settings.amazon_otp_secret,
            oauth_login=False,
        )

    def _outputpath(self, relative_path: str) -> str:
        full_path = os.path.join(self._settings.data_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path

    # -- estado --------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return bool(self._login and self._login.status and self._login.status.get("login_successful"))

    @property
    def login(self) -> AlexaLogin | None:
        return self._login

    def status_snapshot(self) -> dict[str, Any]:
        if not self._login:
            return {"state": "not_initialized"}
        return self._describe_status(self._login.status or {})

    @staticmethod
    def _describe_status(status: dict[str, Any]) -> dict[str, Any]:
        if status.get("login_successful"):
            return {"state": "authenticated"}
        if status.get("captcha_required"):
            return {"state": "captcha_required", "captcha_image_url": status.get("captcha_image_url")}
        if status.get("securitycode_required"):
            return {"state": "otp_required"}
        if status.get("verificationcode_required"):
            return {"state": "verification_code_required"}
        if status.get("claimspicker_required"):
            return {
                "state": "choose_verification_method",
                "message": status.get("claimspicker_message"),
            }
        if status.get("authselect_required"):
            return {"state": "choose_otp_device", "message": status.get("authselect_message")}
        if status.get("approval_status") and status.get("approval_status") != "TransactionCompleted":
            return {
                "state": "waiting_for_app_approval",
                "message": status.get("message"),
            }
        if status.get("login_failed"):
            return {
                "state": "failed",
                "reason": status.get("login_failed"),
                "message": status.get("message") or status.get("error_message"),
            }
        if status:
            return {"state": "in_progress", "message": status.get("message")}
        return {"state": "not_authenticated"}

    # -- fluxo de login --------------------------------------------------

    async def start_login(self) -> dict[str, Any]:
        """Inicia (ou reinicia do zero) o fluxo de autenticação. É o que o botão
        'Reautenticar' da interface dispara."""
        async with self._lock:
            if self._login is None:
                self._login = self._new_login()
            await self._login.reset()
            return await self._drive_login({})

    async def submit_challenge(self, data: dict[str, str]) -> dict[str, Any]:
        """Envia a resposta do usuário a um desafio pendente (CAPTCHA, código
        OTP, escolha de método de verificação etc.)."""
        async with self._lock:
            if self._login is None:
                raise SessionExpiredError("Nenhum login em andamento. Chame POST /auth/login primeiro.")
            return await self._drive_login(data)

    async def _drive_login(self, data: dict[str, str]) -> dict[str, Any]:
        assert self._login is not None
        await self._login.login(data=data)
        for _ in range(_MAX_AUTO_STEPS):
            status = self._login.status or {}
            if status.get("login_successful") or status.get("login_failed"):
                break
            if any(status.get(flag) for flag in _CHALLENGE_FLAGS):
                break
            # Passo puramente mecânico (redirect, polling de aprovação no app,
            # etc.) que não depende de entrada do usuário: seguimos sozinhos.
            await self._login.login(data={})
        return self.status_snapshot()

    # -- uso pela API de lista -----------------------------------------

    async def get_authenticated_login(self) -> AlexaLogin:
        if not self.is_authenticated:
            raise SessionExpiredError(
                "A sessão da Amazon expirou ou ainda não foi autenticada. "
                "Use o botão 'Reautenticar' na interface web para renová-la."
            )
        assert self._login is not None
        return self._login

    async def health_check(self, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and (now - self._last_health_check) < self._settings.healthcheck_cache_seconds:
            return {"authenticated": self._last_health_ok, "cached": True, **self.status_snapshot()}

        self._last_health_check = now
        if not self.is_authenticated:
            self._last_health_ok = False
            return {"authenticated": False, "cached": False, **self.status_snapshot()}

        assert self._login is not None
        try:
            ok = await self._login.test_loggedin(rebuild_session=False)
        except Exception:
            logger.exception("Erro ao verificar se a sessão da Amazon ainda é válida")
            ok = False

        self._last_health_ok = ok
        if not ok:
            logger.warning(
                "A sessão da Amazon expirou (cookies inválidos ou revogados). "
                "É necessário reautenticar pela interface web."
            )
        return {"authenticated": ok, "cached": False, **self.status_snapshot()}
