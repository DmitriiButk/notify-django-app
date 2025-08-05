import logging
from django import forms
from django.http import HttpRequest
from django.contrib import admin
from django.utils.html import format_html
from typing import List, Optional, Any, Set

from .models import Notification, NotificationLog, UserProfile
from notification_app.models import NotificationChannel
from celery_app.tasks import send_notification

logger = logging.getLogger(__name__)


class NotificationForm(forms.Form):
    """Форма для создания и отправки уведомлений."""

    title = forms.CharField(label='Заголовок', max_length=200)
    message = forms.CharField(label='Сообщение', widget=forms.Textarea)

    CHANNELS: List[tuple[str, str]] = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
    ]
    channels = forms.MultipleChoiceField(
        label='Каналы отправки',
        choices=CHANNELS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text='Если не выбрать каналы, система попробует все доступные каналы по порядку'
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Административный интерфейс для управления профилями пользователей."""

    list_display = ('user', 'email', 'phone_number', 'telegram_chat_id')
    search_fields = ('user__username', 'email', 'phone_number')
    fields = ('user', 'email', 'phone_number', 'telegram_chat_id')


class NotificationLogInline(admin.TabularInline):
    """Встроенное представление логов уведомлений на странице уведомления."""

    model = NotificationLog
    extra = 0
    readonly_fields = ('channel', 'status', 'error_message', 'created_at')
    can_delete = False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Административный интерфейс для управления уведомлениями."""

    list_display = ('id', 'user', 'title', 'is_delivered', 'created_at', 'status_badge')
    list_filter = ('is_delivered', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('is_delivered', 'created_at')
    inlines = [NotificationLogInline]
    actions = ['resend_notification']

    def _get_available_channels(self, user) -> List[str]:
        """
        Получает список доступных каналов связи для пользователя.

        Args:
            user: Пользователь, для которого определяются каналы

        Returns:
            Список строковых идентификаторов доступных каналов
        """
        available_channels = []

        try:
            profile = UserProfile.objects.get(user=user)

            if profile.email:
                available_channels.append(NotificationChannel.EMAIL)
            if profile.phone_number:
                available_channels.append(NotificationChannel.SMS)
            if profile.telegram_chat_id:
                available_channels.append(NotificationChannel.TELEGRAM)
        except UserProfile.DoesNotExist:
            logger.warning(f"Профиль не найден для пользователя {user.id}")

        return available_channels

    def _send_notification_task(self, request: HttpRequest, notification: Notification,
                                channels: List[str]) -> bool:
        """
        Запускает асинхронную задачу отправки уведомления.

        Args:
            request: HTTP-запрос администратора
            notification: Объект уведомления для отправки
            channels: Список каналов для отправки

        Returns:
            Флаг успешности постановки задачи в очередь
        """
        try:
            logger.info(f"Отправляем уведомление ID={notification.id} по каналам: {channels}")

            send_notification.delay(
                user_id=notification.user.id,
                title=notification.title,
                message=notification.message,
                channels=channels,
                notification_id=notification.id
            )

            self.message_user(request, "Уведомление поставлено в очередь на отправку")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления ID={notification.id}: {e}",
                         exc_info=True)
            self.message_user(request, f"Возникла ошибка при отправке: {e}", level="ERROR")
            return False

    def save_model(self, request: HttpRequest, obj: Notification, form: Any, change: bool) -> None:
        """
        Сохраняет модель и отправляет новое уведомление.

        Args:
            request: HTTP-запрос администратора
            obj: Объект уведомления
            form: Форма админки
            change: True если объект изменяется, False если создается новый
        """
        super().save_model(request, obj, form, change)

        if not change:
            available_channels = self._get_available_channels(obj.user)

            if not available_channels:
                logger.warning(f"Нет доступных каналов для отправки уведомления ID={obj.id}")
                self.message_user(
                    request,
                    "Уведомление создано, но не может быть отправлено: нет доступных каналов",
                    level="WARNING"
                )
                return

            self._send_notification_task(request, obj, available_channels)

    def resend_notification(self, request: HttpRequest, queryset) -> None:
        """
        Действие для повторной отправки выбранных уведомлений.

        Args:
            request: HTTP-запрос администратора
            queryset: Набор выбранных уведомлений
        """
        count = 0
        for notification in queryset:
            available_channels = self._get_available_channels(notification.user)

            if not available_channels:
                logs = NotificationLog.objects.filter(notification=notification)
                previous_channels = list(logs.values_list('channel', flat=True).distinct())
                if previous_channels:
                    available_channels = previous_channels

            if not available_channels:
                logger.warning(f"Нет доступных каналов для отправки уведомления ID={notification.id}")
                self.message_user(
                    request,
                    f"Не удалось отправить ID={notification.id}: нет доступных каналов",
                    level="ERROR"
                )
                continue

            if self._send_notification_task(request, notification, available_channels):
                count += 1

        self.message_user(request, f'Поставлено в очередь повторных отправок: {count} уведомлений')

    resend_notification.short_description = "Повторно отправить выбранные уведомления"

    def status_badge(self, obj: Notification) -> str:
        """
        Форматирует HTML-бейдж статуса уведомления.

        Args:
            obj: Объект уведомления

        Returns:
            HTML-код для отображения статусного бейджа
        """
        if obj.is_delivered:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 8px; border-radius: 5px;">Доставлено</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; '
            'padding: 3px 8px; border-radius: 5px;">Не доставлено</span>'
        )

    status_badge.short_description = 'Статус'

    def has_change_permission(self, request: HttpRequest, obj: Optional[Notification] = None) -> bool:
        """
        Определяет право на изменение уведомления.

        Args:
            request: HTTP-запрос администратора
            obj: Объект уведомления или None

        Returns:
            True только для списка уведомлений, False для конкретного уведомления
        """
        return obj is None


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Административный интерфейс для просмотра логов уведомлений."""

    list_display = ('notification', 'channel', 'status', 'created_at')
    list_filter = ('status', 'channel', 'created_at')
    search_fields = ('notification__title', 'notification__user__username')
    readonly_fields = ('notification', 'channel', 'status', 'error_message', 'created_at')

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Запрещает добавление логов вручную."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[NotificationLog] = None) -> bool:
        """Запрещает изменение логов."""
        return False
