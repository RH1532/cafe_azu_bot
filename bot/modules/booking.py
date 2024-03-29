from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.constants import ButtonCallbackData, UserFlowState
from crud.order import CurrentOrder

from .start import start_bot


async def booking_menu_show(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if query:
        await query.answer()
        await query.delete_message()

    keyboard = [
        [
            InlineKeyboardButton(
                '✅ Кафе'
                if context.user_data['order'].cafe
                else 'Выбрать кафе',
                callback_data=ButtonCallbackData.BOOKING_SELECT_CAFE,
            ),
            InlineKeyboardButton(
                 '✅ Дата'
                 if context.user_data['order'].from_date
                 else 'Выбрать дату',
                 callback_data=ButtonCallbackData.BOOKING_SELECT_DATE,
            ),
        ],
        [
            InlineKeyboardButton(
                '✅ Меню'
                if context.user_data['order'].menu
                else 'Выбрать меню',
                callback_data=ButtonCallbackData.BOOKING_SELECT_SETS,
            ),
        ],
        [
            InlineKeyboardButton(
                'Отмена', callback_data=ButtonCallbackData.BOOKING_CANCEL
            ),
            InlineKeyboardButton(
                'Оплатить', callback_data=ButtonCallbackData.BOOKING_OK
            ),
        ],
    ]

    current_order: CurrentOrder = context.user_data['order']

    info_message = 'Вы выбрали:\n'
    info_message += str(current_order)
    info_message += '\nВыберите следующее действие:'

    context.user_data['prev_stage'] = UserFlowState.BOOKING

    if update.message:
        await update.message.reply_text(
            info_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
        )
    else:
        await context.bot.send_message(
            update.effective_chat.id,
            info_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
        )

    return UserFlowState.BOOKING


async def booking_menu_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    await query.delete_message()

    current_order: CurrentOrder = context.user_data['order']
    current_order.clear()

    await start_bot(update, context)

    return UserFlowState.START
