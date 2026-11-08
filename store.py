import json
import os
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "db.json"

_db: dict = {"guilds": {}, "posts": {}}


def load() -> None:
    global _db
    if DATA_FILE.exists():
        _db = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _db.setdefault("guilds", {})
        _db.setdefault("posts", {})


def _save() -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_db, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, DATA_FILE)


def get_guild(guild_id: int) -> dict | None:
    return _db["guilds"].get(str(guild_id))


def set_guild(guild_id: int, data: dict) -> None:
    _db["guilds"][str(guild_id)] = data
    _save()


def get_post(thread_id: int) -> dict | None:
    return _db["posts"].get(str(thread_id))


def save_post(post: dict) -> None:
    _db["posts"][str(post["thread_id"])] = post
    _save()


def delete_post(thread_id: int) -> None:
    if _db["posts"].pop(str(thread_id), None) is not None:
        _save()


def posts_in_guild(guild_id: int) -> list[dict]:
    posts = [p for p in _db["posts"].values() if p["guild_id"] == guild_id]
    return sorted(posts, key=lambda p: p["created_at"], reverse=True)
