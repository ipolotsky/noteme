import contextlib
import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

BOT_MSG_KEY = "_bot_msg_id"


async def reply_and_cleanup(
    message: Message,
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    data = await state.get_data()
    bot_msg_id = data.get(BOT_MSG_KEY)
    chat_id = message.chat.id

    if bot_msg_id:
        try:
            await message.bot.edit_message_text(  # type: ignore[union-attr]
                text=text,
                chat_id=chat_id,
                message_id=bot_msg_id,
                reply_markup=reply_markup,
            )
            if message.message_id != bot_msg_id:
                with contextlib.suppress(Exception):
                    await message.delete()
            return
        except Exception:
            pass

    msg = await message.answer(text, reply_markup=reply_markup)
    await state.update_data(**{BOT_MSG_KEY: msg.message_id})
    if message.message_id != msg.message_id:
        with contextlib.suppress(Exception):
            await message.delete()
