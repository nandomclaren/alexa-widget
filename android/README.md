# Lista Alexa (app Android)

App Android nativo (Kotlin, sem Compose/Glance/Retrofit — só bibliotecas
padrão do AndroidX) com um **widget de tela inicial** que mostra e gerencia a
lista de compras exposta pelo backend em `../app` (o serviço FastAPI).

> ⚠️ Este projeto foi escrito sem acesso a um ambiente com Android SDK para
> compilar/testar (o sandbox onde foi gerado não tem o SDK nem rede liberada
> para os servidores da Google). O código foi revisado com cuidado, mas a
> primeira compilação real vai acontecer no seu Android Studio — se der algum
> erro, me manda a mensagem que eu ajusto.

## O que o app faz

- **Widget de tela inicial**: lista os itens, toque no ícone à esquerda marca
  como comprado, toque no "✕" remove, botão "+" abre um diálogo rápido pra
  adicionar item sem abrir o app, botão de atualizar força um refresh. O
  widget também se atualiza sozinho a cada ~30 min (mínimo permitido pelo
  Android).
- **Tela do app** (`MainActivity`): onde você configura a URL do servidor e o
  Bearer token, testa a conexão, e também dá pra ver/adicionar/marcar/remover
  itens direto por ali.
- **Reautenticação**: o app **não reimplementa** a tela de login/CAPTCHA/OTP
  da Amazon — o botão "Abrir login no navegador" só abre a URL do servidor no
  navegador, que já tem essa tela pronta (a mesma interface web do backend).
  Isso mantém o app simples e evita duplicar aquela lógica toda.

## Por que não usa Retrofit/OkHttp/Compose

De propósito: como não dava pra compilar aqui pra validar, preferi manter a
superfície de dependências mínima (`androidx.core`, `androidx.appcompat`,
`material`) e usar só `HttpURLConnection` + `org.json`, que já vêm no
Android — menos coisa que pode dar incompatibilidade de versão no seu
ambiente. Se quiser trocar por Retrofit/Compose depois, é só pedir.

## Como abrir e compilar

1. Abra o **Android Studio** (Hedgehog/2023.1+ recomendado, mas versões mais
   novas também funcionam).
2. **File → Open** e selecione a pasta `android/` deste repositório (não a
   raiz do repo).
3. Deixe o Gradle sincronizar (o Android Studio baixa o wrapper e o SDK
   necessário automaticamente na primeira vez).
4. Espere o build inicial terminar sem erros.

## Como instalar no seu celular

- **Com o celular conectado por USB** (com depuração USB ativada em
  Configurações → Opções do desenvolvedor): clique em **Run ▶** no Android
  Studio com o celular selecionado como destino.
- **Sem cabo/Android Studio por perto**: em **Build → Generate Signed Bundle
  / APK → APK**, gere um APK, transfira pro celular (Drive, e-mail, cabo) e
  instale manualmente (pode precisar permitir "instalar de fontes
  desconhecidas" no Android).

Requer Android 8.0 (API 26) ou superior.

## Configurando o app

1. Abra o app **"Lista Alexa"**.
2. Em **URL do servidor**, cole a URL pública do backend (ex.: a do Railway,
   `https://seuapp.up.railway.app` — sem barra no final).
3. Em **Bearer token**, cole o mesmo `BEARER_TOKEN` do `.env` do backend.
4. Toque em **Salvar configurações**.
5. Toque em **Testar conexão** — deve mostrar "Amazon: autenticado ✅" se o
   backend já tiver uma sessão válida, ou o estado atual caso contrário.
6. Se precisar (re)autenticar, toque em **Abrir login no navegador** e siga o
   fluxo (igual ao descrito no README do backend).

## Adicionando o widget à tela inicial

1. Toque e segure em uma área vazia da tela inicial do Android.
2. Toque em **Widgets**.
3. Procure por **Lista Alexa** e arraste o widget **"Lista de compras"** para
   a tela.
4. Redimensione se quiser ver mais itens de uma vez.

O widget usa as mesmas configurações (URL/token) salvas no app — não precisa
configurar de novo.

## Estrutura do projeto

```
android/
  app/src/main/java/com/alexawidget/app/
    MainActivity.kt                  # tela de configurações + lista
    AddItemActivity.kt               # diálogo rápido de adicionar (botão "+" do widget)
    SettingsStore.kt                 # SharedPreferences (URL + token)
    ApiClient.kt                     # chamadas HTTP à API do backend
    ShoppingListWidgetProvider.kt    # AppWidgetProvider (monta o widget)
    ShoppingListWidgetService.kt     # RemoteViewsService (liga o widget ao factory)
    ShoppingListRemoteViewsFactory.kt# busca os itens e monta cada linha
    WidgetActionReceiver.kt          # trata toques (marcar/remover/atualizar)
  app/src/main/res/
    layout/                          # telas e layouts do widget
    drawable/                        # ícones (todos vetoriais, sem PNG)
    values/, values-night/           # cores/strings/tema (com suporte a modo escuro)
    xml/shopping_list_widget_info.xml# metadata do widget (tamanho, período de atualização)
```

## Problemas conhecidos / limitações

- Sem testes automatizados — não pude rodar nada localmente.
- O ícone do app é um vetor simples gerado à mão; troque à vontade pelo
  Image Asset Studio do Android Studio (botão direito em `res` → New → Image
  Asset) se quiser algo mais elaborado.
- Se a Amazon mudar o formato de resposta do backend (ver troubleshooting no
  README principal), os campos esperados em `ApiClient.parseItem()` também
  podem precisar de ajuste — mas isso é raro, porque o app só fala com o seu
  próprio backend, não direto com a Amazon.
