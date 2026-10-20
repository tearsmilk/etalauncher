# η Эта — Eta

A Minecraft launcher in the Claude-like style of the other apps in this repo (ivory / charcoal, terracotta accent,
serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by `.github/workflows/eta-macos.yml`
(self-test included).

**Stage 1 — the working interface.** Pages, dialogs and local data (accounts, instances, settings) work; the
modpack catalog is served by a demo provider with the same shape as Modrinth's search API. Next: real Modrinth /
CurseForge providers, downloading Minecraft + loaders + Java, launching, Microsoft sign-in.

| Page | What it does |
|---|---|
| Загрузка | Splash with the η logo and a progress bar while the launcher starts |
| Главная | Greeting, banner of the selected instance, **Играть**, instance switcher, game folder, recent instances, launcher news |
| Сборки → Каталог | Modrinth-like browser: search, sources (Modrinth / CurseForge), loader chips (Fabric / Forge / NeoForge / Quilt), game version, categories, sort, «show more»; project page (description, versions); install dialog → creates an instance |
| Сборки → Мои сборки | Instance cards: play, select, open folder, rename, copy, delete; «Создать сборку» (name, game version, loader) |
| Аккаунты | Offline accounts (nickname 3–16 `[A-Za-z0-9_]`, UUID = `UUID.nameUUIDFromBytes("OfflinePlayer:" + name)` like vanilla offline servers), procedural pixel heads, select / copy UUID / delete; Microsoft tab reserved |
| Настройки | Game folder, memory slider (system RAM), Java (auto-detect / browse), JVM args, window size, full screen, theme, close on launch, console, default source, parallel downloads |

## Files

`eta/accounts.py` · `eta/instances.py` · `eta/catalog.py` (DemoProvider; real providers plug in behind `search()`
/ `project()` / `versions()`) · `eta/widgets.py` (pixel heads, block icons, banner) · `eta/ui.py`.
Data lives in `~/Library/Application Support/Eta` (`settings.json`, `accounts.json`, `instances.json`).

## Run

```bash
cd eta
pip install -r requirements.txt
python run.py              # the launcher
python run.py --selftest   # headless checks (offline UUID, validation, catalog filters, every page and dialog)
```

## Design

Figma file «Эта — UI» (team Lotus): `design/figma/01_ui_kit.js`, `design/figma/02_screens.js`.
