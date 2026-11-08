from urllib.parse import quote, unquote, urlparse

import discord

TAG_DEFS = {
    "need": ("Need", "📥"),
    "offer": ("Offer", "📤"),
    "open": ("Open", "🟢"),
    "filled": ("Filled", "✅"),
}


def wiki_url(item: str) -> str:
    return "https://wiki.warframe.com/w/" + quote(item.strip().replace(" ", "_"), safe="_()'")


def item_link(item: str) -> str:
    item = item.strip()
    if item.startswith(("http://", "https://")):
        parsed = urlparse(item)
        name = unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1]).replace("_", " ") or parsed.netloc
        return f"[{name}]({item})"
    return f"[{item}]({wiki_url(item)})"


def _ansi_header(label: str, color: int) -> str:
    return f"```ansi\n\u001b[1;{color}m{label}\u001b[0m\n```"


def post_content(p: dict) -> str:
    parts: list[str] = []
    if p.get("item"):
        parts.append(f"🔗 {item_link(p['item'])}")
    if p.get("need"):
        parts += [_ansi_header("[need]", 31), p["need"]]
    if p.get("offer"):
        parts += [_ansi_header("[offer]", 32), p["offer"]]
    if p.get("notes"):
        parts += ["**Notes**", p["notes"]]
    status = "✅ **FILLED**" if p["status"] == "filled" else "🟢 Open"
    parts.append(f"-# Posted by <@{p['owner_id']}> · {status}")
    return "\n".join(parts)[:2000]


def thread_name(p: dict) -> str:
    prefix = "[FILLED] " if p["status"] == "filled" else ""
    return (prefix + p["title"])[:100]


def tags_for(p: dict, forum: discord.ForumChannel, cfg: dict) -> list[discord.ForumTag]:
    wanted = []
    if p.get("need"):
        wanted.append("need")
    if p.get("offer"):
        wanted.append("offer")
    wanted.append("filled" if p["status"] == "filled" else "open")
    tags = []
    for key in wanted:
        tag = forum.get_tag(cfg["tags"].get(key, 0))
        if tag:
            tags.append(tag)
    return tags[:5]
