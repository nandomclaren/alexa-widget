"""Modelos Pydantic para request/response da API."""

from typing import Any

from pydantic import BaseModel, Field


class ShoppingItem(BaseModel):
    id: str | None = None
    text: str
    completed: bool = False
    created_date: Any = None


class AddItemRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class LoginChallengeRequest(BaseModel):
    """Campos que a interface pode enviar em resposta a um desafio de login.

    Cada campo corresponde a um tipo de desafio que a Amazon pode pedir; envie
    apenas o(s) relevante(s) para o estado atual retornado por GET /auth/status.
    """

    captcha: str | None = None
    securitycode: str | None = None
    verificationcode: str | None = None
    claimsoption: str | None = None
    authselectoption: str | None = None
