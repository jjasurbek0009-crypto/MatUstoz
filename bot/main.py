"""MatUstoz — Telegram botni ishga tushirish nuqtasi."""

from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import config, db, handlers

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

log = logging.getLogger("matustoz")


async def _post_init(app: Application) -> None:
    await db.init()
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Boshlash"),
            BotCommand("reja", "O'quv rejam"),
            BotCommand("progress", "Progressim"),
            BotCommand("reset", "Noldan boshlash"),
            BotCommand("help", "Yordam"),
        ]
    )
    log.info("MatUstoz ishga tushdi. Model: %s", config.MODEL)


async def _post_shutdown(app: Application) -> None:
    await db.close()


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("reja", handlers.plan_command))
    app.add_handler(CommandHandler("progress", handlers.progress_command))
    app.add_handler(CommandHandler("reset", handlers.reset_command))
    app.add_handler(CallbackQueryHandler(handlers.reset_callback, pattern=r"^reset:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL,
            handlers.handle_unsupported,
        )
    )
    app.add_error_handler(handlers.error_handler)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
