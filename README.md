# Сервис уведомлений

## Микросервис для управления и отправки уведомлений пользователям по различным каналам связи (Email, SMS, Telegram).

### Функциональность

- Отправка уведомлений по трём каналам связи
- Асинхронная обработка и отправка сообщений через Celery
- Административный интерфейс для управления уведомлениями
- Логирование всех попыток отправки
- Автоматический выбор доступных каналов

### Стек технологий

- Python 3.12
- Django
- PostgreSQL
- Redis
- Celery
- Docker и Docker Compose
- Twilio для отправки SMS
- Telegram Bot API
-

## Установка и запуск

### Предварительные требования

- Docker и Docker Compose
- Создать бота в Telegram через @BotFather
- Аккаунт в Twilio (для отправки SMS)

### Настройка

Клонируйте репозиторий:

```bash
git clone https://github.com/DmitriiButk/notify-django-app.git
cd notification-service
```

Настройте файл .env:

```plaintext
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token

# PostgreSQL
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django
SECRET_KEY=your_secret_key
DJANGO_DEBUG=True

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email
EMAIL_HOST_PASSWORD=your_password
DEFAULT_FROM_EMAIL=noreply@example.com

# Twilio (SMS)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

```

### Запустите контейнеры:

```bash
docker-compose up -d --build
```

### Создайте суперпользователя:

```bash
docker-compose exec web python manage.py createsuperuser
```

или в самом docker контейнере web, вкладка exec:

```bash
python manage.py createsuperuser
```

### Откройте административную панель по адресу http://localhost:8000/admin/

## Использование

### Создание пользователя и профиля

- Перейдите в раздел Users и создайте нового пользователя
- Перейдите в раздел User profiles и создайте профиль:
- Укажите Email для отправки по электронной почте
- Укажите номер телефона для SMS (в формате 7XXXXXXXXXX)
- Укажите ID чата в Telegram для отправки через бота


### Отправка уведомлений

- Перейдите в раздел Notifications и нажмите "Add Notification"
- Заполните форму:
    - Выберите пользователя
    - Укажите заголовок и текст сообщения
    - Нажмите "Save" — уведомление будет автоматически отправлено

### Дополнительная информация

- Для работы с Telegram ботом пользователь должен сначала инициировать диалог с ботом
- При отправке SMS через Twilio учитывайте ограничения бесплатного аккаунта
- Для тестирования Email в режиме разработки сообщения выводятся в консоль