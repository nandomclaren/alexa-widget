# Alexa Shopping List Bridge

Microserviço em **FastAPI** que expõe a lista de compras nativa da Alexa (a que
a família alimenta por voz, "Alexa, adicione leite à lista de compras") como
uma API REST simples.

## ⚠️ Aviso importante

A Amazon **descontinuou a List Skill API pública**. Não existe mais uma forma
oficial e suportada de ler/escrever a lista de compras padrão por API. Este
projeto funciona fazendo **engenharia reversa de uma sessão web autenticada**:

- Usa a biblioteca [`alexapy`](https://gitlab.com/keatontaylor/alexapy) — a
  mesma base usada pela integração `alexa_media_player` do Home Assistant —
  para lidar com a parte mais chata e sensível a mudanças: login, CAPTCHA,
  código 2FA/OTP e persistência da sessão.
- Usa chamadas HTTP diretas, autenticadas pelos cookies dessa sessão, contra
  o endpoint interno (não documentado) `/api/todos` que o próprio app/site da
  Alexa usa para renderizar a lista de compras.

Isso significa:

- **Não há garantia de que vai continuar funcionando.** A Amazon pode mudar o
  formato de resposta, o caminho do endpoint, ou exigir verificações extras a
  qualquer momento, sem aviso.
- **Use por sua conta e risco.** Evite fazer requisições em excesso — isso é
  tráfego "fora do padrão" e, em teoria, poderia disparar bloqueios de
  segurança na conta. O serviço já faz cache do health check para reduzir
  chamadas desnecessárias.
- É pensado para **uso doméstico/pessoal** (servidor caseiro, VPS pequena),
  não para expor publicamente na internet sem proteção adicional (veja
  [Segurança](#segurança)).

## Como funciona

1. No startup, o serviço tenta retomar uma sessão salva anteriormente (arquivo
   de cookies em `DATA_DIR`).
2. Se não houver sessão válida, a interface web (`http://localhost:8000/`)
   mostra o status "Não autenticado" e um botão **"🔄 Reautenticar"**.
3. Ao clicar em Reautenticar, o serviço inicia o login com o e-mail/senha do
   `.env`. Se a Amazon pedir CAPTCHA, código 2FA, escolha de método de
   verificação, ou aprovação via notificação no app, a interface mostra o
   formulário correspondente na hora, você responde, e o fluxo continua até
   autenticar (ou falhar, com um motivo explicado na tela).
4. Uma vez autenticado, os cookies são salvos em disco (`DATA_DIR`) e
   reaproveitados nos próximos restarts — na maioria dos casos você só precisa
   passar por esse fluxo interativo de vez em quando (a sessão costuma durar
   dias/semanas; configurar `AMAZON_OTP_SECRET` evita ter que digitar o código
   2FA manualmente sempre que reautenticar).
5. As chamadas à lista de compras (`GET/POST/DELETE /api/lists/shopping...`)
   reaproveitam essa mesma sessão autenticada.

## Requisitos

- Docker + Docker Compose (recomendado), **ou** Python 3.12+ para rodar local.
- Uma conta Amazon associada a pelo menos um dispositivo Alexa da casa.

## Configuração

1. Copie `.env.example` para `.env` e preencha:

   ```bash
   cp .env.example .env
   ```

   | Variável | Descrição |
   |---|---|
   | `AMAZON_DOMAIN` | Domínio regional da conta: `amazon.com.br`, `amazon.com`, `amazon.fr`, `amazon.de`, `amazon.co.uk`, etc. |
   | `AMAZON_EMAIL` / `AMAZON_PASSWORD` | Credenciais da conta Amazon. |
   | `AMAZON_OTP_SECRET` | Opcional. Chave TOTP (base32) de 2FA, se configurada na conta. Preenchendo isso, o serviço gera o código sozinho ao reautenticar. |
   | `BEARER_TOKEN` | Token que protege esta API. Gere com `openssl rand -hex 32`. |
   | `DATA_DIR` | Onde os cookies de sessão ficam salvos (`/data` no Docker). |
   | `AMAZON_TODOS_PATH` | Caminho interno da lista (padrão `/api/todos`); ajuste se a Amazon mudar. |
   | `SHOPPING_LIST_TYPE` | Tipo do item no endpoint interno (padrão `SHOPPING_ITEM`; a lista de tarefas usa `TASK`). |
   | `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` ou `ERROR`. |
   | `LOGIN_DEBUG` | `true` grava HTML das páginas de login em `DATA_DIR` para depurar problemas de login. Contém dados sensíveis — deixe `false` no dia a dia. |

## Rodando com Docker (recomendado)

```bash
docker compose up -d --build
```

O serviço sobe em `http://localhost:8000`. Os cookies de sessão ficam
persistidos em `./data` no host (montado como volume), então sobrevivem a
restarts/updates do container.

Acompanhe os logs:

```bash
docker compose logs -f
```

## Rodando localmente sem Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Primeiro login

1. Acesse `http://localhost:8000/` no navegador.
2. Cole o `BEARER_TOKEN` do `.env` no campo "Token de acesso da API" e clique
   em **Salvar** (fica salvo só no `localStorage` do seu navegador).
3. Clique em **🔄 Reautenticar** e siga o formulário que aparecer (CAPTCHA,
   código 2FA, escolha de dispositivo etc.) até o status virar
   **"Autenticado ✅"**.
4. A lista de compras aparece logo abaixo — dá para adicionar, marcar como
   comprado e remover itens direto pela interface, além de usar a API REST.

## Endpoints da API

Todos (exceto `GET /health`) exigem o header:

```
Authorization: Bearer <BEARER_TOKEN>
```

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/health` | Status do serviço + se a sessão Amazon está válida. Não exige token. |
| `GET` | `/auth/status` | Estado atual do login (autenticado, aguardando CAPTCHA/OTP, etc.). |
| `POST` | `/auth/login` | Inicia/reinicia o login do zero (o que o botão "Reautenticar" chama). |
| `POST` | `/auth/challenge` | Envia a resposta a um desafio pendente. Body: um de `{captcha}`, `{securitycode}`, `{verificationcode}`, `{claimsoption}`, `{authselectoption}`. |
| `POST` | `/auth/continue` | Avança um fluxo que só está aguardando (ex.: aprovação no app), sem enviar dado novo. |
| `GET` | `/api/lists/shopping` | Retorna `[{id, text, completed, created_date}]`. |
| `POST` | `/api/lists/shopping` | Body `{"text": "Leite"}`. Adiciona um item. |
| `DELETE` | `/api/lists/shopping/{item_id}` | Remove um item. |
| `POST` | `/api/lists/shopping/{item_id}/complete` | Marca um item como comprado. |

Exemplo com `curl`:

```bash
TOKEN=coloque-o-bearer-token-aqui

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/lists/shopping

curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "Café"}' http://localhost:8000/api/lists/shopping
```

Quando a sessão da Amazon expira, os endpoints de lista respondem
`401 {"error": "session_expired", "message": "..."}` em vez de dar um erro
genérico — é o sinal para reautenticar pela interface.

## Extraindo cookies manualmente pelo DevTools (alternativa/fallback)

Normalmente você **não precisa fazer isso** — o fluxo de login pela interface
web (botão Reautenticar) cuida de tudo. Mas se o login automático estiver
travando em alguma verificação que a `alexapy` não reconhece, ou se você
preferir gerar a sessão manualmente, é possível "injetar" cookies extraídos do
navegador:

1. No navegador (Chrome/Edge/Firefox), acesse `https://alexa.<seu-domínio>`
   (ex.: `https://alexa.amazon.com.br`) e faça login normalmente.
2. Abra o **DevTools** (`F12` ou `Ctrl+Shift+I`).
3. Vá na aba **Network** (Rede), recarregue a página, e clique em qualquer
   requisição feita para `alexa.<seu-domínio>` (ex.: `things`, `devices-v2`,
   `todos`...).
4. Nos **Request Headers** dessa requisição, copie o valor completo do header
   `Cookie:` (uma string longa tipo `session-id=...; ubid-main=...; at-main=...; sess-at-main=...; csrf=...`).
5. Transforme essa string em um objeto JSON simples de `nome: valor`. Por
   exemplo, `session-id=123; at-main=abc` vira:

   ```json
   {
     "session-id": "123",
     "at-main": "abc"
   }
   ```

   (Inclua o máximo de cookies que conseguir; os mais importantes costumam
   ser `session-id`, `ubid-main`, `at-main`, `sess-at-main` e `csrf`, mas
   quanto mais completo, melhor.)

6. Salve esse JSON no arquivo:

   ```
   <DATA_DIR>/.storage/alexa_media.<AMAZON_EMAIL>.cookies
   ```

   Por exemplo, com `DATA_DIR=/data` (Docker) e `AMAZON_EMAIL=fulano@gmail.com`:

   ```
   data/.storage/alexa_media.fulano@gmail.com.cookies
   ```

7. Reinicie o serviço (`docker compose restart`) ou clique em **Reautenticar**
   na interface — ele vai carregar esses cookies e tentar validar a sessão
   automaticamente, sem passar pelo formulário de login.

Alternativamente, também é possível usar uma extensão do navegador do tipo
"cookie editor/exporter" para exportar os cookies do domínio
`alexa.<seu-domínio>` diretamente em JSON e usar o resultado da mesma forma.

> Cookies extraídos assim expiram como qualquer sessão web normal — quando
> isso acontecer, é só repetir o processo (ou, mais simples, usar o botão
> Reautenticar, que faz login com e-mail/senha do zero).

## Segurança

- O `BEARER_TOKEN` é a única coisa protegendo tanto a sua lista de compras
  quanto, indiretamente, a sessão da sua conta Amazon. Use um valor longo e
  aleatório e não o exponha em logs/repositórios públicos.
- **Não exponha a porta 8000 diretamente na internet.** Se precisar acessar
  de fora de casa, coloque atrás de um reverse proxy com HTTPS (Caddy,
  Traefik, Nginx) e, idealmente, uma camada extra de autenticação/VPN
  (Tailscale, WireGuard).
- O diretório `DATA_DIR`/`./data` contém os cookies de sessão da sua conta
  Amazon — trate como uma credencial. Nunca faça commit dele (já está no
  `.gitignore`).
- `.env` também nunca deve ser commitado (já está no `.gitignore`).

## Troubleshooting

**`GET /health` retorna `"authenticated": false`**
A sessão expirou ou nunca foi criada. Acesse a interface web e clique em
Reautenticar.

**O login trava em algum passo que a interface não reconhece**
Ative `LOGIN_DEBUG=true`, reproduza o problema e olhe os arquivos HTML
gravados em `DATA_DIR` (contêm o HTML exato que a Amazon retornou) para
entender qual verificação está sendo pedida. Depois volte `LOGIN_DEBUG=false`.

**A lista de compras para de funcionar, mas `/auth/status` diz "autenticado"**
Provavelmente a Amazon mudou o formato/caminho do endpoint interno. Confira:
- `AMAZON_TODOS_PATH` e `SHOPPING_LIST_TYPE` no `.env`.
- A função `_normalize_item` em `app/amazon_list_client.py`, que mapeia os
  campos da resposta da Amazon (`id`, `text`, `complete`, `createdDate`, ...)
  para o formato da API. Compare com o JSON real usando `LOGIN_DEBUG`/DevTools
  e ajuste os nomes de campo se necessário.

**Erros `401`/`403` mesmo logo após reautenticar**
Normalmente indica token CSRF ausente/expirado. O serviço já busca o CSRF
automaticamente antes de cada escrita (`add`, `delete`, `complete`); se
persistir, tente Reautenticar novamente do zero.

## Estrutura do projeto

```
app/
  main.py               # rotas FastAPI
  config.py             # configuração via .env
  security.py           # proteção por Bearer token
  session_manager.py    # login/sessão Amazon (via alexapy)
  amazon_list_client.py # chamadas HTTP à lista de compras (/api/todos)
  models.py             # schemas Pydantic
  static/auth.html       # interface web (status + botão Reautenticar + lista)
Dockerfile
docker-compose.yml
.env.example
```
