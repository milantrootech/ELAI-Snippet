# serializers.py
from rest_framework import serializers

class NotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    unread = serializers.BooleanField()
    emailed = serializers.BooleanField()
    deleted = serializers.BooleanField()
    actor = serializers.CharField()
    type = serializers.CharField()
    verb = serializers.CharField()
    timestamp = serializers.DateTimeField()

# funcs.py
def notification_data(notifications) -> list:
    """
    A function to prepare a list based on notifications queryset
    """
    data = [
        {
            "id": notification.id,
            "unread": notification.unread,
            "emailed": notification.emailed,
            "deleted": notification.deleted,
            "actor": str(notification.actor),
            "type": notification.actor_content_type.model,
            "verb": notification.verb,
            "timestamp": notification.timestamp,
        }
        for notification in notifications
    ]
    return data

# views.py
from notifications.models import Notification
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

class NotificationConstantsMessage:
    TRANSACTION_DETAIL_FETCH = "Transaction details fetched successfully!"
    
class GeneralConstantsMessage:
    UNREAD_FIELD_REQUIRED = "The unread field is required."

class NotificationList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(
            recipient=self.request.user
        ).order_by("-timestamp")
        data = notification_data(notifications)
        serializer = NotificationSerializer(data, many=True)

        return Response(
            {
                "data": serializer.data,
                "message": NotificationConstantsMessage.TRANSACTION_DETAIL_FETCH,
            },
            status=status.HTTP_200_OK,
        )

class NotificationTypeList(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if "unread" not in request.data:
            return Response(
                {"message": GeneralConstantsMessage.UNREAD_FIELD_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unread_count = Notification.objects.filter(
            recipient=self.request.user, unread=request.data.get("unread")
        ).count()
        return Response({"unread_count": unread_count}, status=status.HTTP_200_OK)


class MarkNotificationAsRead(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(
                id=pk, recipient=request.user, unread=True
            )
        except Notification.DoesNotExist:
            return Response(
                {"message": NotificationConstantsMessage.NOTIFICATION_NOT_FOUND},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification.unread = False
        notification.save()

        return Response(
            {"message": NotificationConstantsMessage.NOTIFICATION_MARK_AS_READ},
            status=status.HTTP_200_OK,
        )


# urls.py
from django.urls import path

path("list/", NotificationList.as_view(), name="list-notification"),
path("type/", NotificationTypeList.as_view(), name="notification-type"),
path(
    "mark-as-read/<int:pk>/",
    MarkNotificationAsRead.as_view(),
    name="mark-as-read-notification",
),