# η Эта — Eta

A Minecraft launcher in the Claude-like style of the other apps in this repo (ivory / charcoal, terracotta accent,
serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by `.github/workflows/eta-macos.yml`, and
Windows x64, built into a single `Eta.exe` by `.github/workflows/eta-windows.yml` (self-test included in both).

## Windows

Скачайте `Eta-<версия>-windows-x64.exe` из артефактов Actions («Эта — Eta (Windows x64 .exe)») или из релиза
`eta-v*` и запустите — установка не нужна. Сборка не подписана: SmartScreen покажет «Система Windows защитила ваш
компьютер» → «Подробнее» → «Выполнить в любом случае». Данные лаунчера лежат в `%APPDATA%\Eta`; удаление сборки
отправляет её папку в корзину (`send2trash`). Локальная сборка: Python 3.11, `pip install -r requirements-build.txt`,
`pwsh packaging/build_windows.ps1` → `dist/Eta.exe` (скрипт сам делает `.ico` и version info через Qt и прогоняет
`Eta.exe --selftest`).

**Stage 2 — Modrinth.** The catalog searches Modrinth live (API v2: facets for loader / game version / category,
sort, paging, project page with versions); installing a modpack downloads its `.mrpack`, then every client file
from `modrinth.index.json` in parallel (https only, Modrinth/GitHub/GitLab hosts, sha1-checked, no paths outside the
instance), then `overrides/` and `client-overrides/` into `<game folder>/instances/<id>/.minecraft`.

**CurseForge** (`eta/curseforge.py`, Core API v1). Нужен бесплатный ключ: console.curseforge.com → API keys →
«Настройки → Загрузки → API-ключ CurseForge» (или переменная `ETA_CURSEFORGE_KEY`); без ключа источник CurseForge в
каталоге и в «Добавить из…» выключен. В готовые `.exe` / `.dmg` ключ «запекается» при сборке: секрет репозитория
`ETA_CURSEFORGE_KEY` (GitHub → Settings → Secrets and variables → Actions) → `build_*.{sh,ps1}` пишут `eta/_keys.py`
(в .gitignore, в репозиторий не попадает). Порядок: переменная окружения → настройки → запечённый ключ. Поиск сборок по загрузчику / версии / категории / сортировке, страница
проекта (описание приходит HTML), файлы; установка скачивает zip сборки, по `manifest.json` запрашивает файлы
пачками (`POST /mods/files`), раскладывает их по папкам по типу проекта (моды, ресурс-паки, шейдеры), проверяет sha1,
копирует `overrides/`. Файлы, авторы которых запретили скачивание через API, пропускаются, если они необязательные,
иначе установка завершается ошибкой со ссылками — их кладут в `mods/` вручную. Моды, шейдеры, ресурс-паки и
датапаки из CurseForge можно добавлять и в готовые сборки (переключатель Modrinth / CurseForge).

**Stage 3 — the game runs.** «Играть» gets everything from Mojang the way the official launcher does (`eta/launch.py`):
the version JSON, client jar, libraries (rules for macOS, natives extracted for old versions), assets (with the
`virtual` layout for ≤ 1.7.2), the log4j config, and Mojang's own Java runtime for that version (`jre-legacy`,
`java-runtime-beta/gamma/delta` → `~/Library/Application Support/Eta/java/<component>`, lzma-compressed files
with sha1 checks, cut transfers retried). Loaders: Fabric and Quilt from their meta servers; Forge and NeoForge by
running their installer headless (`--installClient`), or unpacking it for old Forge (≤ 1.12). A loader version left
empty means the newest stable / recommended one. The command line fills every `${placeholder}` (offline account,
`-XstartOnFirstThread` on macOS, memory, JVM args, window size, full screen); the game's output goes to a console
in the launch dialog, play time is counted, a crash shows the end of the log. Checked on Linux with Mojang's Java
17: vanilla, Fabric and Forge 1.20.1 and Forge 1.12.2 start up to window creation.

**Look.** Настройки → Оформление: theme, accent colour (presets or any colour), window background (painted scenes,
gradients, your own picture), glass (translucent panels over the blurred background: density, blur, veil), serif /
sans headings, side bar left or right. The side bar folds into an icon rail (« / », ⌘\), the catalog filters
hide with «Фильтры».

| Page | What it does |
|---|---|
| Загрузка | Splash with the η logo and a progress bar while the launcher starts |
| Главная | Greeting, compact card of the selected instance, **Играть** (downloads what is missing, then runs the game), instance switcher, game folder, recent instances, launcher news |
| Сборки → Каталог | Modrinth-like browser: search, sources (Modrinth / CurseForge), loader chips (Fabric / Forge / NeoForge / Quilt), game version, categories, sort, «show more»; project page (description, versions); install dialog → creates an instance |
| Сборки → Мои сборки | Instance cards: play, select, open folder, rename, copy, delete; «Создать сборку» (name, game version, loader) |
| Аккаунты | Offline accounts (nickname 3–16 `[A-Za-z0-9_]`, UUID = `UUID.nameUUIDFromBytes("OfflinePlayer:" + name)` like vanilla offline servers), procedural pixel heads, select / copy UUID / delete; **mc-ru.org** accounts (site login, real skin head, see below); **Microsoft** accounts (device-code login, see below) |
| Настройки | Оформление (see above), game folder, memory slider (system RAM), Java (auto-detect / browse), JVM args, window size, full screen, theme, close on launch, console, update check, default source, parallel downloads |
| Серверы | Community servers from mc-ru.org (bottom of the side menu): icon, address + copy, version, MOTD with `§` colours, live online/latency via the Server List Ping, **Играть** joins the server straight away (see below) |

## Аккаунт mc-ru.org

«Добавить аккаунт → mc-ru.org»: вход по нику или email и паролю от сайта сообщества. Сайт держит
Yggdrasil-совместимый сервер авторизации (`https://mc-ru.org/api/yggdrasil`, спецификация authlib-injector), поэтому
лаунчер получает `accessToken` и UUID, при запуске проверяет сессию (`validate` → `refresh`, токены сохраняются в
`accounts.json`) и добавляет в команду `-javaagent:authlib-injector.jar=https://mc-ru.org/api/yggdrasil` — игра
логинится на сайт и показывает скин и плащ без модов (стандартные 64×64). Сам authlib-injector скачивается с
`authlib-injector.yushi.moe` (sha256, кэш в `<game>/authlib-injector/`).

HD и анимированные скины и плащи приходят через **CustomSkinLoader**: для сборок на Fabric / Quilt / Forge /
NeoForge лаунчер докачивает мод с Modrinth в `mods/` (маркер `eta-csl.json`) и пишет
`CustomSkinLoader/CustomSkinLoader.json` с источником `CustomSkinAPI → https://mc-ru.org/api/csl/` первым в списке.
Отключается в Настройки → Игра («HD-скины и плащи в игре»); на ванили пропускается. Голова на карточке аккаунта и в
боковой панели — настоящая (`/api/users/<ник>/skin.png`), пока не загрузилась — пиксельная заглушка.
Файлы: `eta/mcru.py` (API сайта, authlib-injector), `launch.py` (`mcru_session`, `ensure_csl`, `csl_config`),
`tests/test_mcru.py` (локальный фейковый Yggdrasil).

## Аккаунт Microsoft

«Добавить аккаунт → Microsoft»: лицензионный вход по коду устройства — лаунчер показывает код вида `ABCD-1234`,
кнопки «Открыть microsoft.com/link» и «Скопировать код»; после подтверждения в браузере вход завершается сам.
Цепочка та же, что у официального лаунчера: OAuth device code (`login.microsoftonline.com/consumers`, scope
`XboxLive.signin offline_access`) → Xbox Live (`user.auth.xboxlive.com`) → XSTS (`xsts.auth.xboxlive.com`, relying
party `rp://api.minecraftservices.com/`) → `api.minecraftservices.com/authentication/login_with_xbox` →
`entitlements/mcstore` → `minecraft/profile`. В `accounts.json` хранятся токен Minecraft (`mc_token`, ~24 ч),
`mc_expires`, `refresh_token` Microsoft и `xuid`; перед запуском `msa.ensure_session` продлевает сессию через
refresh token. В команду идут `--accessToken <mc_token> --userType msa --xuid … --clientId <Client ID>`; скин и
плащ отдаёт сам Mojang, модов и authlib-injector не нужно. Голова на карточке — с crafatar.com по UUID.

### Что нужно, чтобы вход заработал

Вкладка «Microsoft» в диалоге выключена, пока у лаунчера нет **Client ID** — идентификатора приложения в Azure:

1. [portal.azure.com](https://portal.azure.com) → Microsoft Entra ID → **App registrations → New registration**.
   Name — например `Eta Launcher`; Supported account types — **Personal Microsoft accounts only**; Redirect URI —
   platform **Mobile and desktop applications**, значение `https://login.microsoftonline.com/common/oauth2/nativeclient`.
2. В созданном приложении: **Authentication → Advanced settings → Allow public client flows = Yes** (без этого
   device code не выдаётся). Секрет клиента не нужен.
3. **API permissions** можно не трогать: `XboxLive.signin` запрашивается динамически как делегированное разрешение
   (при первом входе Microsoft спросит согласие).
4. Скопируйте **Application (client) ID** (вид `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) с страницы Overview.
5. Mojang должна одобрить этот ID для `api.minecraftservices.com`: форма
   [aka.ms/mce-reviewappid](https://aka.ms/mce-reviewappid) (название лаунчера, ссылка на репозиторий, Client ID).
   До одобрения `login_with_xbox` отвечает 403 — лаунчер покажет «Приложение ещё не одобрено Mojang».

Куда положить ID: переменная окружения `ETA_MSA_CLIENT_ID` (удобно для сборок: `env:` в
`.github/workflows/eta-*.yml`) или константа `CLIENT_ID` в `eta/eta/msa.py`. Он не секретный — его можно
коммитить.

Ошибки входа и что они значат: «нет профиля Xbox» — создать на xbox.com; «Xbox Live недоступен в стране»;
«нужна проверка возраста»; «детский аккаунт — добавить в семью»; «На этом аккаунте нет Minecraft: Java Edition»;
«нет профиля Minecraft» — зайти официальным лаунчером и придумать ник; «Код устарел» — нажать «Войти» снова.
Файлы: `eta/msa.py`, `launch.py` (`prepare` → `msa.ensure_session`, `command`), `tests/test_msa.py` (локальный фейк
всей цепочки).

## Серверы

Пункт «Серверы» внизу бокового меню (Ctrl+4) показывает список серверов сообщества: лаунчер берёт его с
`https://mc-ru.org/api/servers` (добавляет админ в кабинете сайта `mc-ru.org/admin`: название, адрес, версия, MOTD,
иконка) и кэширует в `servers.json`, чтобы страница открывалась и без сети. Для каждого сервера в фоне делается
Server List Ping (handshake → status, протокол современных версий) — онлайн, лимит, задержка; если у сервера нет
иконки на сайте, берётся favicon из ответа. MOTD рисуется с цветами `§`.

«Играть» запускает выбранную сборку сразу на сервер: для 1.20+ через `--quickPlayMultiplayer ip:port`, для старых
версий через `--server ip --port port`. Если версия выбранной сборки не совпадает с версией сервера, лаунчер предложит
выбрать другую (подходящие — первыми) или открыть каталог, отфильтрованный по версии. В Discord статус становится
«Играет на <сервер>». Файлы: `eta/servers.py`, `launch.py` (`supports_quick_play`, `command(server=…)`),
`tests/test_servers.py` (фейковый сервер Minecraft на сокете).

## Обновления

При старте (не чаще раза в 6 часов, выключается в Настройки → Лаунчер) лаунчер спрашивает
`https://mc-ru.org/api/launcher/version`; если версия новее `eta.__version__`, на главной появляется полоска
«Доступна версия X — Скачать» (ссылка на `.exe` или `.dmg` под текущую систему), ✕ прячет её до следующей версии.
«Проверить сейчас» — в настройках. Файл: `eta/updates.py`.

## Files

`eta/accounts.py` · `eta/instances.py` · `eta/catalog.py` (DemoProvider) · `eta/modrinth.py` (ModrinthProvider,
`.mrpack` install) · `eta/net.py` (HTTPS via certifi, background runner, icon cache) · `eta/mcru.py` (mc-ru.org) · `eta/msa.py` (Microsoft) · `eta/servers.py` (server list, ping, MOTD) ·
`eta/updates.py` · `eta/launch.py` (Minecraft, Java, loaders, command line) · `eta/backgrounds.py` · `eta/widgets.py` (pixel heads, block icons, banner) · `eta/ui.py`.
Data lives in `~/Library/Application Support/Eta` on macOS, `%APPDATA%\Eta` on Windows (`settings.json`,
`accounts.json`, `instances.json`).

## Run

```bash
cd eta
pip install -r requirements.txt
python run.py              # the launcher
python run.py --selftest   # headless checks (offline UUID, validation, catalog, offline .mrpack install, a full launch — version, Java, loader, assets — from a local server with a fake java, mc-ru.org login against a fake Yggdrasil, glass theme, every page and dialog)
python -m tests.test_mcru  # only the mc-ru.org part
python -m tests.test_servers  # server list ping, MOTD, quick play, update check
```

## Design

Figma file «Эта — UI» (team Lotus): `design/figma/01_ui_kit.js`, `design/figma/02_screens.js`.
