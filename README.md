# Бот для кафе "АЗУ"

### Авторы
- [Ильин Данила](https://github.com/RH1532)
- [Василий Мазаев](https://github.com/Vasiliy-Mazaev)
- [Роман Александров](https://github.com/teamofroman)
- [Искандер Рыскулов](https://github.com/IskanderRRR)

### Заказчик
Кафе татарской кухни "АЗУ" [azu.cafe](http://azu.cafe/)

### Техно-стек
- Python
- Django
- Alembic
- Django
- Nginx

## Развёртывание проекта

Клонировать репозиторий и перейти в него в командной строке:

```
git clone https://github.com/RH1532/cafe_azu_bot_1.git
```

```
cd cafe_azu_bot_1
```

Cоздать и активировать виртуальное окружение:

```
poetry shell
```

Создать контейнеры:

```
docker-compose up -d --build
```

Применить миграции:

```
alembic upgrade head
```

Загрузить тестовые данные:

```
python manage.py loaddata base_data.json
```

### Функционал
1. Выбор даты
2. Выбор адреса кафе 
3. Выбор сета
4. Оплата сета дистанционно
5. Получение подтверждения
6. Напоминание о брони
