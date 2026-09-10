# Alexa Shopping List Bridge

Microserviço em **FastAPI** que expõe a lista de compras nativa da Alexa (a que
a família alimenta por voz, "Alexa, adicione leite à lista de compras") como
uma API REST simples.

## ⚠️ Aviso importante

A Amazon **descontinuou a List Skill API pública** (1º de julho de 2024) e,
mais recentemente, **o próprio painel web clássico da Alexa**
(`alexa.amazon.<domínio>`). Não existe mais nenhuma forma oficial e suportada
de ler/escrever a lista de compras padrão por API. Este projeto funciona
fazendo **engenharia reversa de uma sessão web autenticada**:

- Usa a biblioteca [`alexapy`](https://gitlab.com/keatontaylor/alexapy) só
  para persistência de sessão/cookies (login automático por credenciais
  **não funciona de forma confiável** — veja abaixo — então isso é mais um
  detalhe de implementação do que a peça central).
- Usa chamadas HTTP diretas, autenticadas pelos cookies dessa sessão, contra
  a API interna (não documentada) `/alexashoppinglists/api/...`, que hoje é
  quem realmente serve a lista de compras que os comandos de voz alimentam
  (descoberta via DevTools do navegador — não confundir com o sistema comum
  de Listas/Wish List do site, `/hz/wishlist/...`, que é outra coisa).

Isso significa:

- **Não há garantia de que vai continuar funcionando.** A Amazon pode mudar o
  formato de resposta, o caminho do endpoint, ou exigir verificações extras a
  qualquer momento, sem aviso.
- **O login automático por e-mail/senha (o botão "Reautenticar") pode
  simplesmente não funcionar**, mesmo com credenciais corretas e de qualquer
  rede/IP — a Amazon recusa esse fluxo automatizado silenciosamente,
  devolvendo a mesma tela de login em loop, sem CAPTCHA e sem erro. Na
  prática, o caminho confiável é **autenticar uma vez com um navegador de
  verdade e copiar os cookies pro serviço** (veja
  [Autenticação: navegador real + upload de cookies](#autenticação-navegador-real--upload-de-cookies)).
- **Nem todo marketplace da Amazon tem essa lista de compras disponível.**
  Se a sua conta é, por exemplo, `amazon.com.br`, pode ser que a lista
  simplesmente não exista nesse domínio ainda, e seja necessário usar a
  conta/dispositivo em outro país (`amazon.fr`, `amazon.com`, etc.) — veja
  [Sua lista de compras "sumiu": achando o marketplace certo](#sua-lista-de-compras-sumiu-achando-o-marketplace-certo).
- **Use por sua conta e risco.** Evite fazer requisições em excesso — isso é
  tráfego "fora do padrão" e, em teoria, poderia disparar bloqueios de
  segurança na conta. Por isso o `GET /health` **não** verifica a sessão com
  a Amazon por padrão (só reporta o último estado conhecido); use
  `GET /health?deep=true` quando quiser forçar essa checagem de propósito.
- É pensado para **uso doméstico/pessoal** (servidor caseiro, VPS pequena),
  não para expor publicamente na internet sem proteção adicional (veja
  [Segurança](#segurança)).

## Como funciona

1. No startup, o serviço tenta retomar uma sessão salva anteriormente (arquivo
   de cookies em `DATA_DIR`).
2. Se não houver sessão válida, a interface web (`http://localhost:8000/`)
   mostra o status "Não autenticado" e um botão **"🔄 Reautenticar"**. Vale a
   pena tentar — às vezes completa sozinho, pedindo CAPTCHA/2FA na hora — mas
   **não conte com ele**: na prática, a Amazon costuma recusar esse fluxo
   automatizado (loop de volta pra tela de login, sem erro, mesmo com
   credenciais certas). O caminho confiável é logar num navegador de verdade
   e subir os cookies pro serviço — veja
   [Autenticação: navegador real + upload de cookies](#autenticação-navegador-real--upload-de-cookies).
3. Uma vez autenticado (por qualquer um dos dois caminhos), os cookies são
   salvos em disco (`DATA_DIR`) e reaproveitados nos próximos restarts — você
   só precisa reautenticar de vez em quando (a sessão costuma durar
   dias/semanas).
4. As chamadas à lista de compras (`GET/POST/DELETE /api/lists/shopping...`)
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
   | `AMAZON_DOMAIN` | Domínio regional **onde a lista de compras da Alexa realmente funciona** (nem sempre é o marketplace "principal" da sua conta — veja [aqui](#sua-lista-de-compras-sumiu-achando-o-marketplace-certo)). Ex.: `amazon.fr`, `amazon.com`, `amazon.com.br`, `amazon.de`. |
   | `AMAZON_EMAIL` / `AMAZON_PASSWORD` | Credenciais da conta Amazon. Usadas pelo botão Reautenticar (quando funciona); não são estritamente necessárias se você só for usar o fluxo de upload de cookies. |
   | `AMAZON_OTP_SECRET` | Opcional. Chave TOTP (base32) de 2FA, se configurada na conta. |
   | `BEARER_TOKEN` | Token que protege esta API. Gere com `openssl rand -hex 32`. |
   | `DATA_DIR` | Onde os cookies de sessão ficam salvos. Use `/data` no Docker; `./data` (ou outro caminho local) fora dele — **não** deixe `/data` ao rodar sem Docker, é um caminho do sistema, não vai ter permissão de escrita. |
   | `AMAZON_SHOPPING_LIST_ID` | ID da lista de compras padrão da Alexa (não é opcional). Veja como descobrir o valor [aqui](#sua-lista-de-compras-sumiu-achando-o-marketplace-certo). |
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

## Deploy no Railway

Este projeto sobe direto no [Railway](https://railway.app) a partir do
`Dockerfile` do repositório, sem configuração extra de build.

1. No Railway: **New Project → Deploy from GitHub repo** e selecione este
   repositório (`nandomclaren/alexa-widget`). O Railway detecta o
   `Dockerfile` automaticamente.
2. Em **Variables**, adicione todas as variáveis do `.env.example`
   (`AMAZON_DOMAIN`, `AMAZON_EMAIL`, `AMAZON_PASSWORD`, `AMAZON_OTP_SECRET`,
   `BEARER_TOKEN`, `AMAZON_SHOPPING_LIST_ID`, `LOG_LEVEL`,
   `LOGIN_DEBUG`). **Não** defina `PORT` nem `DATA_DIR` manualmente — o
   Railway injeta `PORT` sozinho e o Dockerfile já usa isso; para
   `DATA_DIR`, use o caminho do volume do passo 3.
3. Em **Settings → Volumes**, adicione um volume persistente montado em, por
   exemplo, `/data`, e defina a variável `DATA_DIR=/data` apontando para
   esse mesmo caminho. **Isso é essencial**: sem volume, os cookies de
   sessão (e o login feito pela interface) somem a cada redeploy.
4. Em **Settings → Networking**, gere um domínio público (Railway cria um
   `*.up.railway.app` com HTTPS automático). Essa é a URL que você vai usar
   nos apps do Android.
5. Depois do primeiro deploy, acesse a URL pública no navegador. Como o
   login automático tende a não funcionar (ver aviso no topo), o caminho
   mais confiável é logar localmente e subir os cookies — veja
   [Autenticação: navegador real + upload de cookies](#autenticação-navegador-real--upload-de-cookies).

> Como o Railway já entrega HTTPS pronto, isso também resolve a recomendação
> de segurança de não expor a API sem TLS — só continue protegendo o
> `BEARER_TOKEN`.

## Widget no Android

Há um app Android nativo dedicado em [`android/`](android/) — Kotlin puro,
sem Compose/Retrofit, com um widget de tela inicial que lista os itens
(marcar como comprado, remover, adicionar), configurável com a URL do
servidor e o `BEARER_TOKEN`. A tela de login/CAPTCHA/OTP não foi duplicada
no app: o botão "Abrir login no navegador" só abre a interface web deste
mesmo backend.

Veja [`android/README.md`](android/README.md) para instruções completas de
build e instalação pelo Android Studio.

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
3. Clique em **🔄 Reautenticar**. Se completar sozinho (às vezes pedindo
   CAPTCHA/2FA, que a interface mostra na hora), ótimo. Se ficar voltando pra
   "Não autenticado" em loop sem erro nenhum, é esperado — pule direto pro
   fluxo de [autenticação por navegador real](#autenticação-navegador-real--upload-de-cookies)
   abaixo.
4. Uma vez autenticado (por qualquer um dos dois caminhos), a lista de
   compras aparece na interface — dá pra adicionar, marcar como comprado e
   remover itens direto por ali, além de usar a API REST.

## Endpoints da API

Todos (exceto `GET /health`) exigem o header:

```
Authorization: Bearer <BEARER_TOKEN>
```

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/health` | Status do serviço. Não exige token. Não bate na Amazon a menos que `?deep=true` seja passado. |
| `GET` | `/auth/status` | Estado atual do login (autenticado, aguardando CAPTCHA/OTP, etc.). |
| `POST` | `/auth/login` | Inicia/reinicia o login do zero por credenciais (o que o botão "Reautenticar" chama). |
| `POST` | `/auth/challenge` | Envia a resposta a um desafio pendente. Body: um de `{captcha}`, `{securitycode}`, `{verificationcode}`, `{claimsoption}`, `{authselectoption}`. |
| `POST` | `/auth/continue` | Avança um fluxo que só está aguardando (ex.: aprovação no app), sem enviar dado novo. |
| `POST` | `/auth/upload-cookies` | Envia cookies extraídos de um navegador logado (ver [Autenticação: navegador real + upload de cookies](#autenticação-navegador-real--upload-de-cookies)). |
| `POST` | `/auth/resume-from-cookies` | Recarrega os cookies salvos em disco e tenta retomar a sessão com eles, sem login por credenciais. |
| `GET` | `/api/lists/shopping` | Retorna `[{id, text, completed, created_date}]`. |
| `POST` | `/api/lists/shopping` | Body `{"text": "Leite"}`. Adiciona um item. |
| `DELETE` | `/api/lists/shopping/{item_id}` | Remove um item. |
| `POST` | `/api/lists/shopping/{item_id}/complete` | Marca um item como comprado (corpo opcional `{"completed": false}` pra desmarcar — o mesmo endpoint faz as duas coisas). |

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

## Sua lista de compras "sumiu": achando o marketplace certo

O painel web clássico da Alexa (`alexa.amazon.<domínio>`) foi descontinuado
pela Amazon. A lista de compras que os comandos de voz alimentam
("Alexa, adicione X à lista de compras") hoje só é alcançável por:

- O **app mobile da Alexa** (sempre funciona, é a referência de verdade).
- Uma página web nova, em `https://www.<domínio>/alexaquantum/sp/alexaShoppingList`
  — mas **isso não está disponível em todo marketplace ainda**. Testamos e
  não funcionava em `amazon.com.br`, mas funcionava em `amazon.fr` com a
  mesma família de conta.

Isso **não é o mesmo sistema** que as Listas/Wish List comuns do site
(`amazon.<domínio>/hz/wishlist/...`, onde você cria listas de desejos
manualmente) — são coisas diferentes, mesmo se parecerem parecidas na
interface. Se você adicionar um item por voz e ele não aparecer na lista que
está vendo no navegador, é bem provável que você esteja olhando o sistema
errado, ou o marketplace errado.

### Passo a passo pra achar a sua

1. No app da Alexa, adicione um item de teste bem específico e fácil de
   reconhecer (ex.: "abacaxi roxo") à lista de compras.
2. Testa abrir `https://www.<domínio>/alexaquantum/sp/alexaShoppingList` no
   navegador, logado na mesma conta, trocando `<domínio>` pelos marketplaces
   que sua conta participa (`amazon.com`, `amazon.com.br`, `amazon.fr`,
   `amazon.de`, `amazon.co.uk`...). O item de teste aparece em algum deles?
3. Achou o domínio certo? Ótimo — é esse que vai no `AMAZON_DOMAIN` do `.env`.
4. **Se seu dispositivo Alexa está registrado num marketplace onde essa
   página não existe** (foi o nosso caso: conta BR sem essa funcionalidade),
   a saída é reconfigurar o dispositivo Alexa físico para usar uma conta de
   outro país onde funcione (ex.: `amazon.fr`), mantendo o **idioma do
   dispositivo em português** (isso é uma configuração separada do país da
   conta — Configurações do dispositivo → ⚙️ → Idioma). Isso significa
   registrar o Echo numa conta Amazon diferente da principal — se você tiver
   uma conta secundária nesse outro país, é bem mais simples; se só tiver a
   conta principal, pondere o impacto (perde rotinas/skills configuradas
   nesse dispositivo, muda o marketplace de compras dele) antes de trocar.

### Descobrindo o `AMAZON_SHOPPING_LIST_ID`

Com a página certa aberta e logada:

1. Abre o **DevTools** (`F12`) → aba **Network** → filtro **Fetch/XHR**.
2. Recarrega a página.
3. Acha a chamada pra `GET /alexashoppinglists/api/getlistitems`. O JSON de
   resposta tem uma única chave de nível superior — essa chave (uma string
   longa terminando em `=`) é o `AMAZON_SHOPPING_LIST_ID`.
4. Cola esse valor no `.env`.

## Autenticação: navegador real + importar cookie (1 clique)

O botão **"Tentar login automático"** faz login usando e-mail/senha, mas a
Amazon costuma **recusar esse fluxo automatizado silenciosamente** —
devolve a mesma tela de login em loop, sem CAPTCHA, sem mensagem de erro,
mesmo com credenciais corretas. Isso acontece **em qualquer rede** (testamos
de datacenter e de rede residencial, mesmo resultado) — não é só uma questão
de IP de nuvem. Não conte com ele; é só um botão de tentativa, não o fluxo
normal.

O caminho que funciona de verdade: autenticar uma vez com um **navegador de
verdade** (que passa por todas as checagens anti-bot normalmente) e importar
os cookies dessa sessão pela própria interface web do serviço — é o card
**"Reautenticar por cookie"** na página inicial (`/`). Esse é o fluxo normal
de manutenção sempre que a sessão expirar (dias/semanas depois), não só um
fallback de emergência.

### Passo a passo (todo pelo navegador, sem terminal)

1. Abre `https://www.<AMAZON_DOMAIN>` (o mesmo domínio do `.env`/das
   variáveis do Railway) numa aba e faz login normalmente.
2. Abre a lista de compras: `https://www.<AMAZON_DOMAIN>/alexaquantum/sp/alexaShoppingList`.
3. Abre o **DevTools** (`F12`) → aba **Network**, deixa a página carregar.
4. Clica na chamada **`getlistitems`** na lista de requisições.
5. Na aba **Headers**, na seção *Request Headers*, copia a linha inteira
   `Cookie: ...` (ou clica com o botão direito na requisição → **Copy → Copy
   as cURL** — os dois formatos funcionam, não precisa escolher).
6. Abre a URL do serviço (local `http://localhost:8000` ou a do Railway) no
   navegador, cola o texto copiado na caixa **"Reautenticar por cookie"** e
   clica em **"⚡ Importar cookie e reautenticar"**.

Pronto — sem converter nada pra JSON, sem `curl`, sem terminal. O status no
topo da página muda pra "Autenticado ✅" na hora se der certo.

### Alternativa via terminal (curl)

Se preferir automatizar/scriptar em vez de usar a interface web, o mesmo
endpoint aceita chamada direta:

```bash
URL=http://localhost:8000
# ou a URL pública, se estiver rodando na nuvem: https://seuapp.up.railway.app
TOKEN=coloque-o-bearer-token-aqui

curl -X POST "$URL/auth/import-cookie-header" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-raw "$(jq -Rs '{cookie_text: .}' <<< 'Cookie: session-id=...; at-acbfr=...; session-token=...')"

curl -H "Authorization: Bearer $TOKEN" "$URL/auth/status"
```

Deve responder `{"state": "authenticated"}`. (Os endpoints antigos
`/auth/upload-cookies` + `/auth/resume-from-cookies`, que exigiam montar o
JSON `{"nome": "valor"}` na mão, continuam funcionando — mas
`/auth/import-cookie-header` faz os dois passos de uma vez e aceita o texto
cru copiado do DevTools direto.)

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
A sessão expirou ou nunca foi criada. Acesse a interface web; se
"Reautenticar" não resolver (ver próximo item), use o fluxo de
[autenticação por navegador real](#autenticação-navegador-real--upload-de-cookies).
Use `?deep=true` se quiser forçar uma verificação real com a Amazon em vez
de só reportar o último estado conhecido.

**Reautenticar fica em loop voltando pra "Não autenticado", sem CAPTCHA nem erro**
Esperado — veja
[Autenticação: navegador real + upload de cookies](#autenticação-navegador-real--upload-de-cookies).

**O login trava em algum passo que a interface não reconhece**
Ative `LOGIN_DEBUG=true`, reproduza o problema e olhe os arquivos HTML
gravados em `DATA_DIR` (contêm o HTML exato que a Amazon retornou) para
entender qual verificação está sendo pedida. Depois volte `LOGIN_DEBUG=false`.

**A lista de compras aparece vazia, ou os itens de voz não aparecem**
Você provavelmente está olhando a lista errada (Wish List em vez da lista
padrão da Alexa) ou configurou o marketplace errado em `AMAZON_DOMAIN`. Veja
[Sua lista de compras "sumiu"](#sua-lista-de-compras-sumiu-achando-o-marketplace-certo).

**A lista de compras para de funcionar, mas `/auth/status` diz "autenticado"**
Provavelmente a Amazon mudou o formato/caminho da API interna. Confira:
- `AMAZON_SHOPPING_LIST_ID` no `.env` ainda é válido (a lista não foi
  recriada/removida).
- A função `_normalize_item` em `app/amazon_list_client.py`, que mapeia os
  campos da resposta da Amazon (`id`, `value`, `completed`, `createdDateTime`)
  para o formato da API. Compare com o JSON real usando o DevTools na página
  `/alexaquantum/sp/alexaShoppingList` e ajuste os nomes de campo se necessário.

**Erros `401`/`403` mesmo logo após subir os cookies**
Os cookies podem estar incompletos (faltou algum na hora de copiar do
DevTools) ou já expirados. Repita o processo de
[autenticação por navegador real](#autenticação-navegador-real--upload-de-cookies).

## Estrutura do projeto

```
app/
  main.py               # rotas FastAPI
  config.py             # configuração via .env
  security.py           # proteção por Bearer token
  session_manager.py    # login/sessão Amazon (via alexapy)
  amazon_list_client.py # chamadas HTTP à lista de compras (/alexashoppinglists/api)
  models.py             # schemas Pydantic
  static/auth.html       # interface web (status + botão Reautenticar + lista)
Dockerfile
docker-compose.yml
.env.example
```
