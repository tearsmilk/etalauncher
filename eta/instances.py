"""Own instances ("сборки"): name, Minecraft version, loader, where it came from. Each lives in
<game_dir>/instances/<id>/ (created when the game files get downloaded — that comes with the real installer)."""
import time
import uuid
from pathlib import Path

from .paths import data_dir, load_json, save_json

MC_VERSIONS = ["26.3", "26.2", "26.1", "1.21.11", "1.21.8", "1.21.4", "1.21.1", "1.20.6", "1.20.4", "1.20.1", "1.19.4", "1.19.2", "1.18.2", "1.17.1", "1.16.5",
               "1.12.2", "1.8.9", "1.7.10"]
LOADERS = {"vanilla": "Vanilla", "fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge", "quilt": "Quilt"}


class InstanceStore:
    def __init__(self, file=None):
        self.file = Path(file) if file else data_dir() / "instances.json"
        self.items = load_json(self.file, [])

    def save(self):
        save_json(self.file, self.items)

    def get(self, iid):
        return next((x for x in self.items if x["id"] == iid), None)

    def add(self, name, mc_version, loader="vanilla", source="own", project=None, mods=0, icon=None, iid=None,
            **extra):
        inst = {"id": iid or uuid.uuid4().hex[:10], "name": name, "mc_version": mc_version, "loader": loader,
                "source": source, "project": project or "", "mods": int(mods), "icon": icon or name,
                "created": time.time(), "last_played": 0, "playtime_min": 0, "memory_mb": 0}
        inst.update(extra)
        self.items.insert(0, inst)
        self.save()
        return inst

    def update(self, iid, **kw):
        inst = self.get(iid)
        if inst:
            inst.update(kw)
            self.save()
        return inst

    def remove(self, iid):
        self.items = [x for x in self.items if x["id"] != iid]
        self.save()

    def recent(self, n=6):
        return sorted(self.items, key=lambda x: (x.get("last_played", 0), x.get("created", 0)), reverse=True)[:n]


def new_id():
    return uuid.uuid4().hex[:10]


def describe(inst):
    loader = LOADERS.get(inst.get("loader"), inst.get("loader", ""))
    parts = [f"{loader} {inst.get('mc_version', '')}".strip()]
    if inst.get("mods"):
        parts.append(f"{inst['mods']} модов")
    pt = int(inst.get("playtime_min") or 0)
    if pt:
        parts.append(f"в игре {pt // 60} ч {pt % 60} мин" if pt >= 60 else f"в игре {pt} мин")
    return " · ".join(parts)
