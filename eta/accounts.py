"""Accounts. For now only offline ("пиратка") accounts: a nickname and the UUID the vanilla server gives an offline
player — UUID.nameUUIDFromBytes("OfflinePlayer:" + name), an MD5 based version-3 UUID."""
import hashlib
import re
import time
import uuid
from pathlib import Path

from .paths import data_dir, load_json, save_json

NAME_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


def offline_uuid(name):
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    h[6] = (h[6] & 0x0F) | 0x30   # version 3
    h[8] = (h[8] & 0x3F) | 0x80   # IETF variant
    return str(uuid.UUID(bytes=bytes(h)))


def validate(name, existing=()):
    """None when the nickname is fine, otherwise a message for the user."""
    name = name or ""
    if not name:
        return "Введите ник"
    if len(name) < 3:
        return "Ник короче 3 символов"
    if len(name) > 16:
        return "Ник длиннее 16 символов"
    if not NAME_RE.match(name):
        return "Только латинские буквы, цифры и «_»"
    if name.lower() in {n.lower() for n in existing}:
        return "Такой аккаунт уже есть"
    return None


class AccountStore:
    def __init__(self, file=None):
        self.file = Path(file) if file else data_dir() / "accounts.json"
        self.items = load_json(self.file, [])

    def save(self):
        save_json(self.file, self.items)

    def names(self):
        return [a["name"] for a in self.items]

    def get(self, uid):
        return next((a for a in self.items if a["uuid"] == uid), None)

    def add_offline(self, name):
        err = validate(name, self.names())
        if err:
            raise ValueError(err)
        acc = {"type": "offline", "name": name, "uuid": offline_uuid(name), "created": time.time(), "last_used": 0}
        self.items.append(acc)
        self.save()
        return acc

    def add_mcru(self, name, uuid_, access_token, client_token, login=""):
        """An mc-ru.org account (site login → Yggdrasil tokens); replaces an older entry with the same uuid."""
        self.items = [a for a in self.items if a["uuid"] != uuid_]
        acc = {"type": "mcru", "name": name, "uuid": uuid_, "access_token": access_token,
               "client_token": client_token, "login": login or name, "created": time.time(), "last_used": 0}
        self.items.append(acc)
        self.save()
        return acc

    def update(self, uid, **kw):
        a = self.get(uid)
        if a:
            a.update(kw)
            self.save()
        return a

    def remove(self, uid):
        self.items = [a for a in self.items if a["uuid"] != uid]
        self.save()

    def touch(self, uid):
        a = self.get(uid)
        if a:
            a["last_used"] = time.time()
            self.save()
