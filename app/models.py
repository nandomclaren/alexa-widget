"""Modelos Pydantic para request/response da API."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ShoppingItem(BaseModel):
    id: Optional[str] = None
    text: str
    completed: bool = False
    created_date: Any = None


class AddItemRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class SetItemCompletedRequest(BaseModel):
    completed: bool = True


class LoginChallengeRequest(BaseModel):
    """Campos que a interface pode enviar em resposta a um desafio de login.

    Cada campo corresponde a um tipo de desafio que a Amazon pode pedir; envie
    apenas o(s) relevante(s) para o estado atual retornado por GET /auth/status.
    """

    captcha: Optional[str] = None
    securitycode: Optional[str] = None
    verificationcode: Optional[str] = None
    claimsoption: Optional[str] = None
    authselectoption: Optional[str] = None
