# Repo notes for Claude

- Эта / Eta (η) — Minecraft launcher (PySide6, Russian UI, Claude-like style: ivory/charcoal, terracotta #D97757 accent, serif headings). Moved here from `tearsmilk/amkawa-lang/eta` with history; the rurukaSuka cosmetics mod stays in `tearsmilk/amkawa-lang/rurukasuka` (releases `rurukasuka-v*`), the site is `tearsmilk/honoka` (mc-ru.org).
- Layout: `run.py` (`--selftest` must stay green), package `eta/`, `packaging/` (macOS .dmg via `build_macos.sh` + `Eta.spec`, Windows .exe via `build_windows.ps1` + `Eta-windows.spec`), `tests/`, `design/figma/*.js` → Figma file «Эта — UI» (team Lotus): update the scripts in the same change as any screen/dialog/component.
- CI: `.github/workflows/eta-macos.yml` / `eta-windows.yml` — build on push, release on tag `eta-v*` or `workflow_dispatch` with `release_version`; the CurseForge key is the repo secret `ETA_CURSEFORGE_KEY`.
