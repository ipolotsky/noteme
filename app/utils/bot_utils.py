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


async def transcribe_voice(message: Message, lang: str, user_id: int = 0) -> str | None:
    from app.agents.whisper import transcribe_audio
    from app.i18n.loader import t

    if message.voice.duration > 60:  # type: ignore[union-attr]
        await message.answer(t("ai.audio_too_long", lang))
        return None

    try:
        file = await message.bot.get_file(message.voice.file_id)  # type: ignore[union-attr]
        bio = await message.bot.download_file(file.file_path)  # type: ignore[union-attr]
        audio_bytes = bio.read()  # type: ignore[union-attr]
        filename = file.file_path.rsplit("/", 1)[-1] if file.file_path else "voice.oga"
        text = await transcribe_audio(audio_bytes, filename=filename, user_id=user_id)
        if not text.strip():
            await message.answer(t("ai.audio_empty", lang))
            return None
        return text
    except Exception:
        logger.exception("Voice transcription failed")
        await message.answer(t("errors.unknown", lang))
        return None


async def get_message_text(message: Message, lang: str, user_id: int = 0) -> str | None:
    if message.text:
        return message.text
    if message.voice:
        return await transcribe_voice(message, lang, user_id=user_id)
    return None
