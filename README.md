# Warframe Trade Board Bot

Members create want/offer posts via buttons, the bot turns them into forum posts with `[need]` / `[offer]`,
and the community can respond with **🙋 I can help**.

## Setup

1. **Create the bot:** https://discord.com/developers/applications → New Application → *Bot* → copy the token.
   No privileged intents are required.
2. **Invite it:** *OAuth2 → URL Generator* → scopes `bot` + `applications.commands`, permissions:
   View Channels, Send Messages, Send Messages in Threads, Create Public Threads,
   Manage Threads, Manage Channels (for the forum tags), Embed Links, Read Message History.
3. **Run it:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   copy .env.example .env
   .venv\Scripts\python bot.py
   ```
4. **In Discord:** create a forum channel (e.g. `#trade`), then in a channel like `#trade-panel` run
   `/setup forum:#trade`. The bot posts the button panel and creates the tags *Need / Offer / Open / Filled*.

Tip: deny "Create Posts" for `@everyone` in the forum so all posts go through the bot
(replying inside posts stays allowed).

## Features

| Button | What it does |
|---|---|
| 📝 New post | Form: title, item, need (what you want to get), offer (what you give), notes |
| 🔍 Search | Searches all open posts |
| 📋 My posts | Lists your own posts |
| 🙋 I can help | Pings the author in the post (once per person) |
| ✏️ Edit | Author or mods can edit the post |
| ✅ Mark filled / 🔁 Reopen | Title gets `[FILLED]`, tag switches, post is archived |

### Item field

The optional item field adds a link at the top of the post. Discord shows a preview of the link,
and its image becomes the post's thumbnail in the forum list.

- **Item name**, e.g. `Okina Prime` → links to `https://wiki.warframe.com/w/Okina_Prime`
- **Full URL**, e.g. `https://warframe.market/items/okina_prime_set` → used as is; the link text
  is taken from the last part of the URL (`okina prime set`)

The name has to match the wiki page title, otherwise the link leads to an empty page and no preview appears.

### need vs. offer

- **[need]** = what you want to **get**
- **[offer]** = what you **give** in return

Selling something? Put the item under **[offer]** and the price (e.g. `200p`) under **[need]**.

## Notes

Data is stored in `data/db.json`. Note: Discord only allows ~2 renames per post every 10 minutes,
so if a post is toggled back and forth quickly, the new title shows up with a delay.
