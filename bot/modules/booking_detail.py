from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from core.constants import ButtonCallbackData, UserFlowState
from crud.worker import Worker
from models.models import Order

from .start import start_bot


async def generate_booking_message(order: Order, worker: Worker):
    cafe = await worker.get_cafe_by_id(order.cafe_id)
    message = (
        f'Номер бронирования: <b>{order.id}</b>\n'
        f'Кафе: <b>{cafe.name} ({cafe.address})</b>\n'
        f'☎️ {cafe.phone}\n'
        f'🌍 {cafe.map_link}\n'
        f'Дата: <b>{order.from_date.strftime("%d.%m.%Y")}</b>\n'
    )

    total_cost = 0
    total_quantity = 0
    menu_message = 'Выбранные сеты:\n'

    for menu_item in await worker.get_menu_by_id(order):
        set_info = await worker.get_sets_by_id(menu_item.set_id)

        menu_message += (
            f'\t- {set_info.name} {menu_item.quantity} шт. '
            f'x {set_info.cost}руб. = '
            f'{menu_item.quantity * set_info.cost} руб.\n'
        )
        total_cost += menu_item.quantity * set_info.cost
        total_quantity += menu_item.quantity

    menu_message += (
        f'\tВсего <b>{total_quantity}</b> сет(а, ов) '
        f'на <b>{total_cost}</b> руб.\n'
    )
    message += menu_message

    return message


async def booking_detail_show(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()
    await query.delete_message()

    user = context.user_data['user']
    worker: Worker = context.user_data['worker']
      
    user_bookings = await worker.get_user_bookings(user)
    context.user_data['user_bookings'] = user_bookings

    current_booking_indx = context.user_data.get('current_booking_indx', 0)

    if user_bookings:
        current_booking = user_bookings[current_booking_indx]
        def pluralize(number, forms):
            if number % 100 in {11, 12, 13, 14}:
                return forms[2]
            rem = number % 10
            if rem == 1:
                return forms[0]
            elif 2 <= rem <= 4:
                return forms[1]
            else:
                return forms[2]
        order_1 = "бронирование"
        order2_4 = "бронирования"
        orders = "бронирований"
        info_message = (
            f'\tУ Вас <b>{len(user_bookings)}</b> '
            f'{pluralize(len(user_bookings), [order_1, order2_4, orders])}.\n'
        )
        info_message += await generate_booking_message(current_booking, worker)
        info_message += f'Для отмены бронирования свяжитесь с администратором.'

        keyboard = [
            [
                 InlineKeyboardButton(
                    'Следующее бронирование ➡️',
                    callback_data=ButtonCallbackData.BOOKING_DETAIL_NEXT,
                ),
            ],
            [
                InlineKeyboardButton(
                    '⬅️ Предыдущее бронирование',
                    callback_data=ButtonCallbackData.BOOKING_DETAIL_PREV,
                ),
            ],
            [
                InlineKeyboardButton(
                    'Назад',
                    callback_data=ButtonCallbackData.BOOKING_DETAIL_BACK,
                ),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    'Назад',
                    callback_data=ButtonCallbackData.BOOKING_DETAIL_BACK,
                ),
            ]
        ]
        info_message = 'У вас нет активных бронирований.'

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

    return UserFlowState.BOOKING_DETAIL


async def bookings_switching(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    current_booking_indx = context.user_data.get('current_booking_indx', 0)
    user_bookings = context.user_data['user_bookings']
    
    if query.data == ButtonCallbackData.BOOKING_DETAIL_NEXT:
        current_booking_indx = (current_booking_indx + 1) % len(user_bookings)
    elif query.data == ButtonCallbackData.BOOKING_DETAIL_PREV:
        current_booking_indx = (current_booking_indx - 1) % len(user_bookings)

    context.user_data['current_booking_indx'] = current_booking_indx
    
    await booking_detail_show(update, context)

    return UserFlowState.BOOKING_DETAIL


async def booking_detail_back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    await query.delete_message()

    await start_bot(update, context)

    return UserFlowState.START
