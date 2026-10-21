"""Modpack catalog. `DemoProvider` serves built-in example projects with the same shape as Modrinth's
/v2/search hits, so the pages work today; `ModrinthProvider` / `CurseForgeProvider` will plug in behind the same
`search()` / `project()` API (facets: project_type:modpack, categories:<loader>, versions:<mc>)."""
import random

from .instances import MC_VERSIONS

CATEGORIES = {   # Modrinth's modpack categories
    "adventure": "Приключения", "challenging": "Испытания", "combat": "Сражения", "kitchen-sink": "Всего понемногу",
    "lightweight": "Лёгкие", "magic": "Магия", "multiplayer": "Мультиплеер", "optimization": "Оптимизация",
    "quests": "Квесты", "technology": "Техника",
}
LOADER_TAGS = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge", "quilt": "Quilt"}
SOURCES = {"modrinth": "Modrinth", "curseforge": "CurseForge", "own": "Своя"}
SORTS = {"relevance": "По релевантности", "downloads": "По скачиваниям", "follows": "По подписчикам",
         "newest": "Сначала новые", "updated": "Недавно обновлённые"}

_DEMO = [
    ("Чистый прирост", "optimum-plus", "lumen", "Только оптимизация: больше FPS, быстрее загрузка, ванильный геймплей.",
     ["optimization", "lightweight"], ["fabric", "quilt"], 38),
    ("Звёздный путь", "starpath", "orbita", "Космос, ракеты и терраформинг планет. Квестовая линия на 400 глав.",
     ["technology", "quests", "adventure"], ["neoforge"], 212),
    ("Тихая гавань", "quiet-harbor", "mira", "Уютное выживание: фермы, готовка, рыбалка и красивые деревни.",
     ["adventure", "lightweight"], ["fabric"], 96),
    ("Глубины", "the-depths", "korund", "Хардкорное подземелье: свет — ресурс, а пещеры живут своей жизнью.",
     ["challenging", "adventure", "challenging"], ["forge", "neoforge"], 154),
    ("Мастерская", "workshop", "gearwright", "Шестерёнки, конвейеры и автоматизация без электричества.",
     ["technology", "quests"], ["forge", "fabric"], 187),
    ("Арканум", "arcanum", "nyx", "Школы магии, ритуалы и подземелья с боссами-волшебниками.",
     ["magic", "adventure"], ["neoforge", "forge"], 241),
    ("Всё и сразу", "everything-at-once", "atlas-team", "Больше 400 модов: техника, магия, приключения, измерения.",
     ["kitchen-sink", "multiplayer"], ["neoforge"], 421),
    ("Скайблок: Облака", "cloud-skyblock", "cumulus", "Один остров в небе и квесты, которые ведут к звёздам.",
     ["quests", "challenging"], ["fabric", "forge"], 132),
    ("Средневековье", "medieval-age", "castellan", "Замки, рыцари, торговля и живые королевства.",
     ["adventure", "multiplayer"], ["forge"], 208),
    ("Север", "north", "fjord", "Суровая зима, температура, голод и выживание в тундре.",
     ["adventure", "challenging"], ["fabric"], 118),
    ("Кинолента", "cinematic", "lumen", "Шейдеры, физика, анимации — для красивых видео и скриншотов.",
     ["optimization", "lightweight"], ["fabric", "quilt"], 64),
    ("Острова", "islands", "archipel", "Генерация архипелагов, корабли и морские приключения.",
     ["adventure", "adventure"], ["fabric", "neoforge"], 143),
    ("Индустрия", "industria", "volt", "Энергосети, реакторы и огромные заводы для мультиплеера.",
     ["technology", "multiplayer"], ["neoforge"], 276),
    ("Сказки", "fairy-tales", "mira", "Лёгкая сборка с магией природы, питомцами и уютными биомами.",
     ["magic", "lightweight"], ["fabric"], 87),
    ("Испытание", "the-trial", "ironclad", "Каждый моб сильнее, ресурсы скуднее, а награды — дороже.",
     ["challenging", "challenging"], ["forge"], 99),
    ("Вечерний сервер", "evening-server", "atlas-team", "Готовая сборка для сервера с друзьями: голос, карты, приваты.",
     ["multiplayer", "adventure"], ["fabric", "neoforge"], 72),
]


def _make_demo():
    rng = random.Random(7)
    out = []
    for i, (title, slug, author, desc, cats, loaders, mods) in enumerate(_DEMO):
        cats = list(dict.fromkeys(cats))
        versions = sorted(rng.sample(MC_VERSIONS[:9], rng.randint(1, 3)), key=MC_VERSIONS.index)
        out.append({
            "project_id": f"demo{i:02d}", "slug": slug, "title": title, "author": author, "description": desc,
            "categories": cats, "loaders": loaders, "game_versions": versions, "mods": mods,
            "downloads": int(10 ** rng.uniform(4.2, 7.1)), "follows": int(10 ** rng.uniform(2.5, 5.0)),
            "date_created": 1_600_000_000 + rng.randint(0, 120_000_000),
            "date_modified": 1_730_000_000 + rng.randint(0, 40_000_000),
            "source": "modrinth" if i % 3 else "curseforge",
            "body": (f"{desc}\n\n**В сборке:** {mods} модов, настроенные квесты и конфиги.\n\n"
                     "* Совместима с серверами\n* Рекомендуется 6 ГБ памяти и больше\n* Обновляется каждый месяц"),
        })
    return out


def fmt_count(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + " млн"
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + " тыс."
    return str(n)


class DemoProvider:
    name = "demo"

    def __init__(self):
        self.items = _make_demo()

    def search(self, query="", sources=(), loaders=(), version="", categories=(), sort="relevance", offset=0,
               limit=20):
        q = (query or "").strip().lower()
        hits = []
        for p in self.items:
            if sources and p["source"] not in sources:
                continue
            if loaders and not set(loaders) & set(p["loaders"]):
                continue
            if version and version not in p["game_versions"]:
                continue
            if categories and not set(categories) <= set(p["categories"]):
                continue
            score = 0
            if q:
                hay = " ".join([p["title"], p["description"], p["author"], p["slug"]]).lower()
                if not all(w in hay for w in q.split()):
                    continue
                score = (3 if q in p["title"].lower() else 0) + (1 if q in p["description"].lower() else 0)
            hits.append((score, p))
        key = {"downloads": lambda h: -h[1]["downloads"], "follows": lambda h: -h[1]["follows"],
               "newest": lambda h: -h[1]["date_created"], "updated": lambda h: -h[1]["date_modified"],
               "relevance": lambda h: (-h[0], -h[1]["downloads"])}[sort if sort in SORTS else "relevance"]
        hits.sort(key=key)
        total = len(hits)
        return [p for _, p in hits[offset:offset + limit]], total

    def project(self, slug):
        return next((p for p in self.items if p["slug"] == slug or p["project_id"] == slug), None)

    def versions(self, slug):
        p = self.project(slug)
        if not p:
            return []
        out = []
        for mc in reversed(p["game_versions"]):
            for loader in p["loaders"]:
                for k, ver in enumerate(("1.4.2", "1.4.0", "1.3.7")):
                    out.append({"name": f"{p['title']} {ver}", "version": ver, "mc": mc, "loader": loader,
                                "type": "release" if k == 0 else "beta" if k == 1 else "release",
                                "date": p["date_modified"] - k * 86400 * 21})
        return out
