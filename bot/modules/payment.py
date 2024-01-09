import datetime
from asyncio import sleep

import pytz

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
)
from telegram.ext import ContextTypes

from core.config import settings
from core.constants import ButtonCallbackData, UserFlowState
from crud.order import CurrentOrder
from crud.worker import Worker

from .booking import booking_menu_show
from .start import start_bot
from .timers import (
    timer_for_payment,
    remove_job_if_exists,
    reservation_reminder
)


async def payment_show_dialog(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
):
    payment_message_id = context.user_data.get('payment_message_id', None)

    query = update.callback_query

    if payment_message_id:
        await query.message.reply_text(
            'Похоже, что окно оплаты уже показано.\nПосмотрите выше.'
        )
        return UserFlowState.PAYMENT_CHOOSE

    current_order: CurrentOrder = context.user_data.get('order')
    worker: Worker = context.user_data.get('worker')
    basket = context.user_data.get('basket')

    if not (basket and current_order.cafe and current_order.from_date):
        await query.answer(('Вы указали не все детали бронирования'),
                           show_alert=True)
        await booking_menu_show(update, context)
        return UserFlowState.BOOKING

    free_places = await worker.get_free_places(current_order.cafe,
                                               current_order.from_date)
    if free_places <= 0:
        await query.answer(
                    (
                        ('Свободные места закончились, '
                         'измените детали бронирования')
                    ),
                    show_alert=True
                )
        await booking_menu_show(update, context)
        return UserFlowState.BOOKING

    await query.answer()
    await query.delete_message()

    await worker.save_order(current_order)

    cafe = current_order.cafe

    booking_date = current_order.from_date.strftime("%d.%m.%Y")

    booking_id = current_order.order_id

    prices = []
    payment_price = 0
    for menu_item in current_order.menu.values():
        cur_cost = menu_item[1] * menu_item[0].cost
        payment_price += cur_cost
        prices.append(
            LabeledPrice(
                label=f'{menu_item[0].name} {menu_item[1]} шт.',
                amount=cur_cost * 100,
            )
        )

    payment_keyboard = [
        [
            InlineKeyboardButton(f'Оплатить {payment_price} руб.', pay=True),
        ],
        [
            InlineKeyboardButton(
                'Отменить бронь',
                callback_data=ButtonCallbackData.PAYMENT_CANCEL,
            ),
        ],
    ]

    payment_message = await query.message.reply_invoice(
        title=f'Оплата бронирования № {booking_id}',
        description=(
            f'Оплата бронирования в кафе {cafe.name} ' f'на {booking_date}'
        ),
        payload=f'payment_booking_{booking_id}',
        provider_token=settings.payment_provider_token,
        currency='RUB',
        prices=prices,
        reply_markup=InlineKeyboardMarkup(payment_keyboard),
        need_email=True,
        need_name=True,
        need_phone_number=True,
    )

    text = "Для оплаты бронирования у вас есть 15 минут"
    message = await query.message.reply_text(text)
    await sleep(3)

    context.user_data['payment_message_id'] = payment_message.message_id
    chat_id = update.effective_message.chat_id
    current_message = message.id
    timer_minutes = 15                        # 15 минут

    context.job_queue.run_once(
        timer_for_payment,
        timer_minutes,
        chat_id=chat_id,
        name=str(chat_id),
        data={
            'count': timer_minutes,
            'message_id': update.effective_message.id,
            'payment_message_id': payment_message.message_id,
            'current_message': current_message,
            'worker': worker,
            'current_order': current_order
        },
    )

    return UserFlowState.PAYMENT_CHOOSE


async def payment_successful(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    payment_message_id = context.user_data.get('payment_message_id', None)

    if payment_message_id:
        await context.bot.delete_message(
            update.message.chat_id,
            payment_message_id,
        )
        await context.bot.delete_message(     # Удаление сообщения с таймером
            update.message.chat_id,
            payment_message_id + 1,
        )
        del context.user_data['payment_message_id']

    current_order: CurrentOrder = context.user_data['order']
    worker: Worker = context.user_data['worker']

    cafe = current_order.cafe
    booking_date = current_order.from_date.strftime("%d.%m.%Y")

    await update.message.reply_text(
        'Спасибо, оплата за бронирование '
        f'<b>№{current_order.order_id}</b> прошла успешно.\n'
        f'Кафе: <b>{cafe.name} {cafe.address}</b>\n'
        f'Дата: <b>{booking_date}</b>',
        parse_mode='HTML',
    )

    current_order.is_paid = True

    await worker.update_payment_status(
        order_id=current_order.order_id,
        is_paid=True,
    )
    await update.message.reply_text(
        f'Ваше бронирование:\n{str(current_order)}',
        parse_mode='HTML',
    )

    chat_id = update.effective_message.chat_id
    remove_job_if_exists(str(chat_id), context)
    data_order = current_order.from_date
    tz_kazan = pytz.timezone('Europe/Moscow')
    name_timer = f'Напоминание о бронировании {chat_id}'
    time_message = data_order.replace(
        day=data_order.day - 1,
        hour=13,
        minute=0,
        second=0).astimezone(tz_kazan)

    if (data_order - datetime.datetime.now()) > datetime.timedelta(hours=11):
        context.job_queue.run_once(
            reservation_reminder,
            time_message,
            chat_id=chat_id,
            name=name_timer,
            data={}
        )
        await worker.save_timer_job(
            chat_id=chat_id,
            name=name_timer,
            data={},
            scheduled_time=data_order
        )

    context.user_data['last_order'] = current_order
    await start_bot(update, context)

    return UserFlowState.START


async def payment_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.delete_message()
    del context.user_data['payment_message_id']

    current_order: CurrentOrder = context.user_data['order']
    worker: Worker = context.user_data['worker']

    order_status = await worker.get_cancelled_status(current_order.order_id)
    await worker.update_cancelled_status(
        order_id=current_order.order_id, is_cancelled=True
    )

    chat_id = update.effective_message.chat_id
    cafe = current_order.cafe
    booking_date = current_order.from_date.strftime("%d.%m.%Y")

    if not order_status:
        remove_job_if_exists(str(chat_id), context)
        await context.bot.delete_message(
            chat_id,
            update.effective_message.message_id + 1
        )
        await worker.update_cancelled_status(
            order_id=current_order.order_id,
            is_cancelled=True
        )
        await query.message.reply_text(
            f'Бронирование№ <b>{current_order.order_id}</b> отменено:\n'
            f'Кафе: <b>{cafe.name} {cafe.address}</b> \n'
            f'Дата: <b>{booking_date}</b>',
            parse_mode='HTML',
        )

    await start_bot(update, context)

    return UserFlowState.START


async def payment_precheckout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Answers the PreQecheckoutQuery"""

    current_order: CurrentOrder = context.user_data['order']

    booking_id = current_order.order_id

    query = update.pre_checkout_query

    if query.invoice_payload != f'payment_booking_{booking_id}':
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)
