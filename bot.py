import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

import store
from render import TAG_DEFS
from views import PanelView, PostView, panel_embed

log = logging.getLogger("trader")


class TraderBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents(guilds=True))
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        store.load()
        self.add_view(PanelView())
        self.add_view(PostView(filled=False))
        self.add_view(PostView(filled=True))

        dev_guild = os.getenv("DEV_GUILD_ID")
        if dev_guild:
            guild = discord.Object(int(dev_guild))
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
            except discord.Forbidden:
                log.error(
                    "Can't register commands in guild %s. Is the bot on that server and was it "
                    "invited with the 'applications.commands' scope? Is DEV_GUILD_ID correct?", dev_guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("Logged in as %s (%s)", self.user, self.user.id)

    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent) -> None:
        store.delete_post(payload.thread_id)


bot = TraderBot()


async def ensure_tags(forum: discord.ForumChannel) -> dict[str, int]:
    by_name = {t.name.lower(): t for t in forum.available_tags}
    tags = list(forum.available_tags)
    changed = False
    for key, (name, emoji) in TAG_DEFS.items():
        if name.lower() not in by_name:
            tags.append(discord.ForumTag(name=name, emoji=emoji, moderated=key in ("open", "filled")))
            changed = True
    if changed:
        await forum.edit(available_tags=tags[:20])
        forum = await forum.guild.fetch_channel(forum.id)
        by_name = {t.name.lower(): t for t in forum.available_tags}
    return {key: by_name[name.lower()].id for key, (name, _) in TAG_DEFS.items() if name.lower() in by_name}


@bot.tree.command(name="setup", description="Post the trade panel here and choose the forum for trade posts")
@app_commands.describe(forum="Forum channel where trade posts are created")
@app_commands.default_permissions(manage_guild=True)
@app_commands.guild_only()
async def setup(interaction: discord.Interaction, forum: discord.ForumChannel):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        tag_ids = await ensure_tags(forum)
    except discord.Forbidden:
        await interaction.followup.send(
            f"❌ I need **Manage Channels** in {forum.mention} to create the tags.", ephemeral=True)
        return
    store.set_guild(interaction.guild.id, {"forum_id": forum.id, "tags": tag_ids})
    await interaction.channel.send(embed=panel_embed(), view=PanelView())
    await interaction.followup.send(f"✅ Panel posted. Trade posts will go to {forum.mention}.", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.exception("Command error", exc_info=error)
    msg = "⚠️ Something went wrong."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN missing – copy .env.example to .env and fill it in.")
    bot.run(token, root_logger=True)


if __name__ == "__main__":
    main()
