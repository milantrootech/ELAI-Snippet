# models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import ActivatorModel, TimeStampedModel

from django.contrib.auth import get_user_model

User = get_user_model()

class Chat(ActivatorModel, TimeStampedModel):
    uuid = models.UUIDField(null=True, blank=True, verbose_name=_("UUID"))
    message = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Message")
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="chats",
        verbose_name="User",
    )

    class Meta:
        verbose_name = "Chat"
        verbose_name_plural = "Chats"

# serializers.py
from rest_framework import serializers

class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]

class ChatSerializer(serializers.ModelSerializer):
    user = UserResponseSerializer()

    class Meta:
        model = Chat
        fields = ["id", "user", "message", "created"]


# pagination.py
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000

# views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

class ChatConstantsMessage:
    CHAT_CREATED_SUCCESSFULLY = "Chat deleted successfully."

class ChatHistoryView(viewsets.ModelViewSet):
    queryset = Chat.objects.filter(status=ActivatorModel.ACTIVE_STATUS).order_by(
        "-created"
    )
    serializer_class = ChatSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["id", "user"]
    pagination_class = StandardResultsSetPagination

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"message": ChatConstantsMessage.CHAT_CREATED_SUCCESSFULLY},
            status=status.HTTP_200_OK,
        )

# urls.py
from rest_framework.routers import DefaultRouter

app_name = "chat_api"

router = DefaultRouter()
router.register(r"history", ChatHistoryView, basename="chat-history")

urlpatterns = router.urls
