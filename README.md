# η Эта — Eta

A Minecraft launcher in the Claude-like style of the other apps in this repo (ivory / charcoal, terracotta accent,
serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by `.github/workflows/eta-macos.yml`
(self-test included).

**Stage 2 — Modrinth.** The catalog searches Modrinth live (API v2: facets for loader / game version / category,
sort, paging, project page with versions); installing a modpack downloads its `.mrpack`, then every client file
from `modrinth.index.json` in parallel (https only, Modrinth/GitHub/GitLab hosts, sha1-checked, no paths outside the
instance), then `overrides/` and `client-overrides/` into `<game folder>/instances/<id>/.minecraft`. CurseForge is
still a demo provider.

**Stage 3 — the game runs.** «Играть» gets everything from Mojang the way the official launcher does (`eta/launch.py`):
the version JSON, client jar, libraries (rules for macOS, natives extracted for old versions), assets (with the
`virtual` layout for ≤ 1.7.2), the log4j config, and Mojang's own Java runtime for that version (`jre-legacy`,
`java-runtime-beta/gamma/delta` → `~/Library/Application Support/Eta/java/<component>`, lzma-compressed files
with sha1 checks, cut transfers retried). Loaders: Fabric and Quilt from their meta servers; Forge and NeoForge by
running their installer headless (`--installClient`), or unpacking it for old Forge (≤ 1.12). A loader version left
empty means the newest stable / recommended one. The command line fills every `${placeholder}` (offline account,
`-XstartOnFirstThread` on macOS, memory, JVM args, window size, full screen); the game's output goes to a console
in the launch dialog, play time is counted, a crash shows the end of the log. Checked on Linux with Mojang's Java
17: vanilla, Fabric and Forge 1.20.1 and Forge 1.12.2 start up to window creation. Next: CurseForge, Microsoft
sign-in.

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
| Аккаунты | Offline accounts (nickname 3–16 `[A-Za-z0-9_]`, UUID = `UUID.nameUUIDFromBytes("OfflinePlayer:" + name)` like vanilla offline servers), procedural pixel heads, select / copy UUID / delete; **mc-ru.org** accounts (site login, real skin head, see below); Microsoft tab reserved |
| Настройки | Оформление (see above), game folder, memory slider (system RAM), Java (auto-detect / browse), JVM args, window size, full screen, theme, close on launch, console, default source, parallel downloads |

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

## Files

`eta/accounts.py` · `eta/instances.py` · `eta/catalog.py` (DemoProvider) · `eta/modrinth.py` (ModrinthProvider,
`.mrpack` install) · `eta/net.py` (HTTPS via certifi, background runner, icon cache) · `eta/mcru.py` (mc-ru.org) · `eta/launch.py` (Minecraft, Java, loaders,
command line) · `eta/backgrounds.py` · `eta/widgets.py` (pixel heads, block icons, banner) · `eta/ui.py`.
Data lives in `~/Library/Application Support/Eta` (`settings.json`, `accounts.json`, `instances.json`).

## Run

```bash
cd eta
pip install -r requirements.txt
python run.py              # the launcher
python run.py --selftest   # headless checks (offline UUID, validation, catalog, offline .mrpack install, a full launch — version, Java, loader, assets — from a local server with a fake java, mc-ru.org login against a fake Yggdrasil, glass theme, every page and dialog)
python -m tests.test_mcru  # only the mc-ru.org part
```

## Design

Figma file «Эта — UI» (team Lotus): `design/figma/01_ui_kit.js`, `design/figma/02_screens.js`.
