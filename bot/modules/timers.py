import datetime
from asyncio import sleep

import pytz

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from core.db import get_async_session
from crud.worker import Worker
from core.constants import ButtonCallbackData


async def reservation_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        text='Напоминание о бронировании, любой текст, любые переменные',
        chat_id=job.chat_id
    )


def remove_job_if_exists(
        name: str,
        context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def timer_for_payment(context: ContextTypes.DEFAULT_TYPE, ) -> None:
    """Отправлет таймер для оплаты"""

    job = context.job
    timer_count = job.data['count']
    timer_message = job.data['current_message']
    payment_message = job.data['payment_message_id']
    worker = job.data['worker']
    current_order = job.data['current_order']

    while timer_count > 5:
        order_status = await worker.get_cancelled_status(current_order.order_id)
        if order_status:
            break
        else:
            await context.bot.edit_message_text(
                text=f'До отмены бронирования осталось '
                     f'<b> {timer_count} минут </b>',
                chat_id=job.chat_id,
                message_id=timer_message,
                parse_mode='HTML'
            )
            await sleep(60)
            timer_count -= 1

    seconds = timer_count * 60
    while seconds > 0:
        order_status = await worker.get_cancelled_status(current_order.order_id)
        if order_status:
            break
        else:
            m, s = divmod(seconds, 60)
            await context.bot.edit_message_text(
                text=f'До отмены бронирования осталось '
                     f'<b> {m} минут {s:02} секунд </b>',
                chat_id=job.chat_id,
                message_id=timer_message,
                parse_mode='HTML'
            )
            await sleep(1)
            seconds -= 1

    if seconds == 0:
        cafe = current_order.cafe
        booking_date = current_order.from_date.strftime("%d.%m.%Y")

        await context.bot.delete_message(job.chat_id, timer_message)

        await context.bot.send_message(
            text=f'Бронирование№ <b>{current_order.order_id}</b> отменено.:\n'
                 f'Истекло время на оплату'
                 f'Кафе: <b>{cafe.name} {cafe.address}</b>\n'
                 f'Дата: <b>{booking_date}</b>',
            chat_id=job.chat_id,
            parse_mode='HTML'
        )

        await worker.update_cancelled_status(
            order_id=current_order.order_id,
            is_cancelled=True
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    'Начать сначала',
                    callback_data=ButtonCallbackData.PAYMENT_CANCEL,
                ),
            ],
        ]
        await context.bot.send_message(
            job.chat_id,
            'Выберите дальнейшее действие:',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        await context.bot.delete_message(job.chat_id, payment_message)


async def timers_for_start_bot(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """Запускает сохраненные напоминания если они не просрочены """

    worker = context.user_data.get('worker', None)
    if not worker:
        a_gen = get_async_session()
        session = await anext(a_gen)
        worker = Worker(session)
    await worker.load_data()

    context.user_data['worker'] = worker

    timers = await worker.get_all_timer_jobs()

    for timer in timers:
        chat_id = timer.chat_id
        name = timer.name
        data = timer.data
        scheduled_time = timer.scheduled_time

        if (scheduled_time - datetime.datetime.now()) > datetime.timedelta(
                hours=11):
            tz_kazan = pytz.timezone('Europe/Moscow')
            time_message = scheduled_time.replace(
                day=scheduled_time.day - 1,
                hour=13,
                minute=0,
                second=0).astimezone(tz_kazan)
            context.job_queue.run_once(
                reservation_reminder,
                time_message,
                data=data,
                chat_id=chat_id,
                name=name,
            )
