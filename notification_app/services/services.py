import re
import requests
import logging
from django.conf import settings
from django.core.mail import send_mail
from typing import Tuple, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений через различные каналы связи."""

    @staticmethod
    def send_email(email: str, title: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Отправляет уведомление по электронной почте.

        Args:
            email: Email-адрес получателя
            title: Заголовок письма
            message: Текст сообщения

        Returns:
            Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
        """
        try:
            if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                return False, "Некорректный email-адрес"

            email_host = getattr(settings, 'EMAIL_HOST', None)
            email_user = getattr(settings, 'EMAIL_HOST_USER', None)

            if not email_host or email_host == 'smtp.example.com' or not email_user:
                logger.error("Настройки SMTP сервера не настроены")
                return False, "Настройки SMTP сервера не настроены"

            if getattr(settings, "EMAIL_BACKEND", "") == 'django.core.mail.backends.console.EmailBackend':
                logger.warning("Используется консольный бэкенд для email (без реальной отправки)")

            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL')
            send_mail(
                subject=title,
                message=message,
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False
            )
            logger.info(f"Email успешно отправлен на {email}")
            return True, None
        except Exception as e:
            logger.error(f"Ошибка отправки email: {str(e)}")
            return False, str(e)

    @staticmethod
    def send_sms(phone: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Отправляет SMS-уведомление через Twilio.

        Args:
            phone: Номер телефона получателя
            message: Текст сообщения

        Returns:
            Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
        """
        try:
            if not phone:
                return False, "Номер телефона не указан"

            phone_cleaned = re.sub(r'\D', '', phone)
            if len(phone_cleaned) < 10:
                return False, f"Некорректный формат номера: {phone}"

            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN')
            from_number = getattr(settings, 'TWILIO_PHONE_NUMBER')

            if not account_sid or not auth_token or not from_number:
                logger.error("Не настроены параметры Twilio SMS-сервиса")
                return False, "Не настроены параметры Twilio SMS-сервиса"

            client = Client(account_sid, auth_token)
            message_obj = client.messages.create(
                body=message,
                from_=from_number,
                to=f"+{phone_cleaned}"
            )
            logger.info(f"SMS успешно отправлено, SID: {message_obj.sid}")
            return True, None

        except TwilioRestException as e:
            logger.warning(f"Ошибка Twilio: {e.msg}")
            return False, f"Ошибка Twilio: {e.msg}"
        except Exception as e:
            logger.error(f"Ошибка при отправке SMS: {str(e)}")
            return False, str(e)

    @staticmethod
    def send_telegram(chat_id: str, message: str) -> Tuple[bool, Optional[str]]:
        """
        Отправляет уведомление через Telegram Bot API.

        Args:
            chat_id: Идентификатор чата Telegram
            message: Текст сообщения

        Returns:
            Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
        """
        try:
            if not chat_id:
                return False, "ID чата Telegram не указан"

            bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN')
            if not bot_token:
                logger.error("Не настроен токен Telegram бота")
                return False, "Не настроен токен Telegram бота"

            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }

            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info(f"Сообщение в Telegram успешно отправлено")
                return True, None
            else:
                error_description = result.get("description", "Неизвестная ошибка")
                logger.warning(f"Ошибка Telegram: {error_description}")
                return False, error_description

        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP при отправке в Telegram: {str(e)}")
            return False, f"Ошибка сервиса Telegram: {str(e)}"
        except Exception as e:
            logger.error(f"Ошибка при отправке в Telegram: {str(e)}")
            return False, str(e)
