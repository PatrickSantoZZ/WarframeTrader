import logging
import time

import discord

import store
from render import post_content, tags_for, thread_name

log = logging.getLogger("trader")
NO_PINGS = discord.AllowedMentions.none()


async def reply(interaction: discord.Interaction, text: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def get_forum(guild: discord.Guild) -> tuple[dict | None, discord.ForumChannel | None]:
    cfg = store.get_guild(guild.id)
    if not cfg:
        return None, None
    forum = guild.get_channel(cfg["forum_id"])
    if forum is None:
        try:
            forum = await guild.fetch_channel(cfg["forum_id"])
        except discord.NotFound:
            return cfg, None
    return cfg, forum


async def get_thread(guild: discord.Guild, thread_id: int) -> discord.Thread:
    return guild.get_thread(thread_id) or await guild.fetch_channel(thread_id)


def can_manage(interaction: discord.Interaction, post: dict) -> bool:
    return interaction.user.id == post["owner_id"] or interaction.permissions.manage_threads


def short(text: str, n: int = 50) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def post_list_embed(title: str, posts: list[dict], empty: str) -> discord.Embed:
    embed = discord.Embed(title=title, color=0x5865F2)
    lines = []
    for p in posts:
        bits = []
        if p.get("need"):
            bits.append(f"**need:** {short(p['need'])}")
        if p.get("offer"):
            bits.append(f"**offer:** {short(p['offer'])}")
        icon = "✅" if p["status"] == "filled" else "🟢"
        line = f"{icon} <#{p['thread_id']}>\n-# {' · '.join(bits)}"
        if sum(len(l) + 1 for l in lines) + len(line) > 3900:
            lines.append(f"… and {len(posts) - len(lines)} more")
            break
        lines.append(line)
    embed.description = "\n".join(lines) if lines else empty
    return embed


class BaseView(discord.ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        log.exception("Error in %s", item, exc_info=error)
        await reply(interaction, "⚠️ Something went wrong. Please try again or ping a mod.")


class PostModal(discord.ui.Modal):

    def __init__(self, post: dict | None = None):
        super().__init__(title="Edit post" if post else "New trade post", timeout=900)
        self.post = post
        p = post or {}
        self.title_in = discord.ui.TextInput(
            label="Title", placeholder="e.g. Razor Mortar Augment Mod",
            max_length=90, default=p.get("title"))
        self.item_in = discord.ui.TextInput(
            label="Item name or link (optional)", placeholder="e.g. Okina Prime – adds a wiki link with picture",
            required=False, max_length=80, default=p.get("item"))
        self.need_in = discord.ui.TextInput(
            label="[need] What do you want to GET?", style=discord.TextStyle.paragraph,
            placeholder="Razor Mortar – from Cephalon Suda (Genius) or Perrin Sequence (Partner)",
            required=False, max_length=800, default=p.get("need"))
        self.offer_in = discord.ui.TextInput(
            label="[offer] What do you GIVE in return?", style=discord.TextStyle.paragraph,
            placeholder="Selling? Put your item here and the price under [need]. E.g. Okina Prime Riven",
            required=False, max_length=800, default=p.get("offer"))
        self.notes_in = discord.ui.TextInput(
            label="Notes (optional)", style=discord.TextStyle.paragraph,
            placeholder="Platform, timezone, IGN, …",
            required=False, max_length=300, default=p.get("notes"))
        for field in (self.title_in, self.item_in, self.need_in, self.offer_in, self.notes_in):
            self.add_item(field)

    def values(self) -> dict:
        return {
            "title": self.title_in.value.strip(),
            "item": self.item_in.value.strip(),
            "need": self.need_in.value.strip(),
            "offer": self.offer_in.value.strip(),
            "notes": self.notes_in.value.strip(),
        }

    async def on_submit(self, interaction: discord.Interaction) -> None:
        data = self.values()
        if not data["need"] and not data["offer"]:
            await reply(interaction, "❌ Please fill in at least **[need]** or **[offer]**.")
            return
        if self.post:
            await self._edit(interaction, data)
        else:
            await self._create(interaction, data)

    async def _create(self, interaction: discord.Interaction, data: dict) -> None:
        cfg, forum = await get_forum(interaction.guild)
        if forum is None:
            await reply(interaction, "❌ The trade board isn't set up. Ask a mod to run `/setup`.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        post = {
            **data,
            "guild_id": interaction.guild.id,
            "owner_id": interaction.user.id,
            "status": "open",
            "helpers": [],
            "created_at": int(time.time()),
        }
        created = await forum.create_thread(
            name=thread_name(post),
            content=post_content(post),
            view=PostView(filled=False),
            applied_tags=tags_for(post, forum, cfg),
            allowed_mentions=NO_PINGS,
        )
        post["thread_id"] = created.thread.id
        post["message_id"] = created.message.id
        store.save_post(post)
        try:
            await created.thread.add_user(interaction.user)
        except discord.HTTPException:
            pass
        await interaction.followup.send(f"✅ Your post is live: {created.thread.mention}", ephemeral=True)

    async def _edit(self, interaction: discord.Interaction, data: dict) -> None:
        post = store.get_post(self.post["thread_id"])
        if post is None:
            await reply(interaction, "❌ This post no longer exists.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        cfg, forum = await get_forum(interaction.guild)
        thread = await get_thread(interaction.guild, post["thread_id"])
        old_name = thread_name(post)
        post.update(data)
        store.save_post(post)

        was_archived = thread.archived
        if was_archived:
            await thread.edit(archived=False)
        await thread.get_partial_message(post["message_id"]).edit(
            content=post_content(post), allowed_mentions=NO_PINGS)
        changes = {}
        if forum is not None:
            changes["applied_tags"] = tags_for(post, forum, cfg)
        if thread_name(post) != old_name:
            changes["name"] = thread_name(post)
        if was_archived:
            changes["archived"] = True
        if changes:
            await thread.edit(**changes)
        await interaction.followup.send("✏️ Post updated.", ephemeral=True)


class SearchModal(discord.ui.Modal, title="Search the trade board"):
    query = discord.ui.TextInput(label="What are you looking for?", placeholder="e.g. Razor Mortar, Red Veil, Arcane …", max_length=80)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        words = self.query.value.lower().split()
        hits = []
        for p in store.posts_in_guild(interaction.guild.id):
            if p["status"] != "open":
                continue
            haystack = " ".join(p.get(k, "") for k in ("title", "item", "need", "offer", "notes")).lower()
            if all(w in haystack for w in words):
                hits.append(p)
        embed = post_list_embed(
            f"🔍 Open posts for “{short(self.query.value, 40)}”", hits,
            "Nothing found. Create a post with **📝 New post** and the community can help!")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PanelView(BaseView):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="New post", emoji="📝", style=discord.ButtonStyle.primary, custom_id="panel:new")
    async def new_post(self, interaction: discord.Interaction, _):
        if store.get_guild(interaction.guild.id) is None:
            await reply(interaction, "❌ The trade board isn't set up. Ask a mod to run `/setup`.")
            return
        await interaction.response.send_modal(PostModal())

    @discord.ui.button(label="Search", emoji="🔍", style=discord.ButtonStyle.secondary, custom_id="panel:search")
    async def search(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(SearchModal())

    @discord.ui.button(label="My posts", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="panel:mine")
    async def mine(self, interaction: discord.Interaction, _):
        posts = [p for p in store.posts_in_guild(interaction.guild.id) if p["owner_id"] == interaction.user.id]
        embed = post_list_embed("📋 Your posts", posts, "You don't have any posts yet.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


def panel_embed() -> discord.Embed:
    return discord.Embed(
        title="🛒 Trade Board",
        description=(
            "Looking for something or have something to offer?\n\n"
            "📝 **New post** – say what you **need** and what you **offer**\n"
            "🔍 **Search** – browse open posts\n"
            "📋 **My posts** – see your own posts\n\n"
            "Others can press **🙋 I can help** on your post – you'll get a ping. "
            "When you're done, press **✅ Mark filled**."
        ),
        color=0x5865F2,
    )


class PostView(BaseView):

    def __init__(self, filled: bool):
        super().__init__(timeout=None)
        buttons = [
            ("I can help", "🙋", discord.ButtonStyle.primary, "post:help", self.on_help, filled),
            ("Edit", "✏️", discord.ButtonStyle.secondary, "post:edit", self.on_edit, False),
        ]
        if filled:
            buttons.append(("Reopen", "🔁", discord.ButtonStyle.secondary, "post:reopen", self.on_reopen, False))
        else:
            buttons.append(("Mark filled", "✅", discord.ButtonStyle.success, "post:filled", self.on_filled, False))
        for label, emoji, style, cid, cb, disabled in buttons:
            btn = discord.ui.Button(label=label, emoji=emoji, style=style, custom_id=cid, disabled=disabled)
            btn.callback = cb
            self.add_item(btn)

    async def on_help(self, interaction: discord.Interaction):
        post = store.get_post(interaction.channel_id)
        if post is None:
            return await reply(interaction, "❌ This post isn't tracked by the bot anymore.")
        if interaction.user.id == post["owner_id"]:
            return await reply(interaction, "That's your own post 😄")
        if post["status"] == "filled":
            return await reply(interaction, "This post is already filled.")
        if interaction.user.id in post["helpers"]:
            return await reply(interaction, "You already offered help – the owner has been pinged.")
        post["helpers"].append(interaction.user.id)
        store.save_post(post)
        await interaction.response.send_message(
            f"🙋 {interaction.user.mention} can help with this! <@{post['owner_id']}>",
            allowed_mentions=discord.AllowedMentions(users=[discord.Object(post["owner_id"])]),
        )

    async def on_edit(self, interaction: discord.Interaction):
        post = store.get_post(interaction.channel_id)
        if post is None:
            return await reply(interaction, "❌ This post isn't tracked by the bot anymore.")
        if not can_manage(interaction, post):
            return await reply(interaction, "Only the author or a mod can edit this post.")
        await interaction.response.send_modal(PostModal(post))

    async def on_filled(self, interaction: discord.Interaction):
        await self._set_status(interaction, "filled")

    async def on_reopen(self, interaction: discord.Interaction):
        await self._set_status(interaction, "open")

    async def _set_status(self, interaction: discord.Interaction, status: str):
        post = store.get_post(interaction.channel_id)
        if post is None:
            return await reply(interaction, "❌ This post isn't tracked by the bot anymore.")
        if not can_manage(interaction, post):
            return await reply(interaction, "Only the author or a mod can change this post.")
        if post["status"] == status:
            return await reply(interaction, "Nothing to change.")
        await interaction.response.defer()
        post["status"] = status
        store.save_post(post)

        thread = await get_thread(interaction.guild, post["thread_id"])
        if thread.archived:
            await thread.edit(archived=False)
        filled = status == "filled"
        await interaction.message.edit(
            content=post_content(post), view=PostView(filled=filled), allowed_mentions=NO_PINGS)

        cfg, forum = await get_forum(interaction.guild)
        changes = {"name": thread_name(post)}
        if forum is not None:
            changes["applied_tags"] = tags_for(post, forum, cfg)
        await thread.edit(**changes)

        if filled:
            await thread.send(f"✅ Marked as **filled** by {interaction.user.mention}. Thanks everyone!",
                              allowed_mentions=NO_PINGS)
            await thread.edit(archived=True)
        else:
            await thread.send(f"🔁 Reopened by {interaction.user.mention}.", allowed_mentions=NO_PINGS)
