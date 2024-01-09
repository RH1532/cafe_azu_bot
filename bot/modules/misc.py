from telegram import Update
from telegram.ext import ContextTypes

from core.constants import UserFlowState


async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит справочное сообщение, если пользователь ввел что-то не то."""
    await update.message.reply_text(
        'Это просто справка',
    )
    return UserFlowState.START


async def spam_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит справочное сообщение, если пользователь ввел что-то не то."""
    await update.message.reply_text(
        'Сори, я не понял...\nНайдите последнее сообщение с кнопками или '
        'выберите `/start`',
    )
