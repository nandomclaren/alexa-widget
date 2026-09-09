"""Configuração do serviço, carregada a partir de variáveis de ambiente/.env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Conta Amazon usada pelo dispositivo Alexa e domínio regional
    # (ex.: amazon.com, amazon.com.br, amazon.fr, amazon.de, amazon.co.uk...)
    amazon_domain: str = "amazon.com.br"
    amazon_email: str
    amazon_password: str = ""
    amazon_otp_secret: str = ""

    # Token simples usado para proteger esta API (Authorization: Bearer <token>)
    bearer_token: str

    # Onde ficam salvos os cookies de sessão e (opcionalmente) arquivos de depuração
    data_dir: str = "/data"

    # Endpoint interno reverso-engenheirado da lista de compras/tarefas da Alexa.
    # A Amazon pode alterar isso sem aviso; ajuste aqui se parar de funcionar.
    amazon_todos_path: str = "/api/todos"
    shopping_list_type: str = "SHOPPING_ITEM"

    request_timeout_seconds: float = 15.0

    # Grava HTML de depuração das páginas de login em data_dir (contém dados
    # sensíveis da conta); mantenha desligado a menos que esteja depurando.
    login_debug: bool = False

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
