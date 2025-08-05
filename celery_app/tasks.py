import logging
from celery import shared_task
from typing import Dict, List, Optional, Any
from django.contrib.auth.models import User

from notification_app.models import Notification, NotificationLog, NotificationChannel
from notification_app.services.services import NotificationService
from notification_app.models import UserProfile

logger = logging.getLogger(__name__)


@shared_task(name='notification_service.send_notification')
def send_notification(user_id: int, title: str, message: str, channels: Optional[List[str]] = None,
                      notification_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Отправляет уведомление пользователю через указанные каналы связи.

    Процесс отправки:
    1. Находит или создает объект уведомления
    2. Определяет доступные каналы связи (email, SMS, Telegram)
    3. Последовательно пытается отправить через каждый канал
    4. Останавливается при первой успешной отправке

    Args:
        user_id: ID пользователя-получателя
        title: Заголовок уведомления
        message: Текст сообщения
        channels: Список каналов для отправки
        notification_id: ID существующего уведомления (для повторной отправки)

    Returns:
        Dict с результатом отправки:
        - status: "success" или "error"
        - notification_id: ID уведомления
        - channel: Канал успешной отправки (при успехе)
        - message: Текст ошибки (при неудаче)
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"Пользователь с ID {user_id} не найден")
        return {"status": "error", "message": f"Пользователь с ID {user_id} не найден"}

    notification = _get_or_create_notification(user, title, message, notification_id)

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        logger.warning(f"Профиль для пользователя {user.username} не найден")
        notification.is_delivered = False
        notification.save()
        return {"status": "error", "notification_id": notification.id, "message": "Профиль пользователя не найден"}

    priority_channels = channels or _get_available_channels(profile)

    if not priority_channels:
        notification.is_delivered = False
        notification.save()
        return {"status": "error", "notification_id": notification.id, "message": "Нет доступных каналов для отправки"}

    for channel in priority_channels:
        success, error_msg = _send_by_channel(channel, profile, title, message)

        NotificationLog.objects.create(
            notification=notification,
            channel=channel,
            status=success,
            error_message=error_msg,
        )

        if success:
            notification.is_delivered = True
            notification.save()
            return {"status": "success", "notification_id": notification.id, "channel": channel}

    notification.is_delivered = False
    notification.save()

    return {"status": "error", "notification_id": notification.id,
            "message": "Не удалось доставить ни по одному каналу"}


def _get_or_create_notification(user: User, title: str, message: str, notification_id: Optional[int]) -> Notification:
    """
    Получает существующее или создает новое уведомление.

    Args:
        user: Пользователь
        title: Заголовок
        message: Текст сообщения
        notification_id: ID существующего уведомления

    Returns:
        Объект уведомления
    """
    if notification_id:
        try:
            return Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            logger.error(f"Уведомление с ID {notification_id} не найдено")
            return None

    return Notification.objects.create(user=user, title=title, message=message)


def _get_available_channels(profile: UserProfile) -> List[str]:
    """
    Определяет доступные каналы связи для профиля пользователя.

    Args:
        profile: Профиль пользователя

    Returns:
        Список доступных каналов
    """
    channels = []

    if profile.email:
        channels.append(NotificationChannel.EMAIL)
    if profile.phone_number:
        channels.append(NotificationChannel.SMS)
    if profile.telegram_chat_id:
        channels.append(NotificationChannel.TELEGRAM)

    return channels


def _send_by_channel(channel: str, profile: UserProfile, title: str, message: str) -> tuple[bool, Optional[str]]:
    """
    Отправляет уведомление по указанному каналу.

    Args:
        channel: Канал отправки
        profile: Профиль пользователя
        title: Заголовок
        message: Текст сообщения

    Returns:
        Кортеж (успех, сообщение об ошибке)
    """
    if channel == NotificationChannel.EMAIL:
        if not profile.email:
            return False, "Email пользователя не указан"
        return NotificationService.send_email(profile.email, title, message)

    elif channel == NotificationChannel.SMS:
        if not profile.phone_number:
            return False, "Номер телефона пользователя не указан"
        return NotificationService.send_sms(profile.phone_number, message)

    elif channel == NotificationChannel.TELEGRAM:
        if not profile.telegram_chat_id:
            return False, "Telegram ID пользователя не указан"
        return NotificationService.send_telegram(profile.telegram_chat_id, message)

    return False, f"Неизвестный канал отправки: {channel}"
