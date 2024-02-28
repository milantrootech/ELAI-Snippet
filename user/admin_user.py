# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "username", "email", "age")

class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "age")

# pagination.py
from rest_framework.pagination import PageNumberPagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000

# utils.py
from django.core.mail import send_mail
class UserConstantsMessage:
    DEFAULT_MAIL_SUCCESS = "Mail sent successfully!"
    ADMIN_CREDENTIALS_NOT_FOUND = "Admin credentials not found!"
   
def send_admin_mail(subject, description, from_email, recipient_list):
    send_mail(subject, description, from_email, recipient_list)
    return UserConstantsMessage.DEFAULT_MAIL_SUCCESS

# views.py
from django.utils.translation import gettext_lazy as _
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, views, status
from rest_framework.mixins import UpdateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from django.conf import settings

class UserView(generics.ListAPIView):
    queryset = User.objects.filter(is_admin=False, is_staff=False).order_by("-id")
    serializer_class = AdminUserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = (IsAuthenticated,)
    filter_backends = [SearchFilter]
    search_fields = ["email"]

class RetrieveDestroyUserById(generics.RetrieveDestroyAPIView, DestroyModelMixin):
    queryset = User.objects.filter(is_admin=False, is_staff=False)
    serializer_class = AdminUserSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultsSetPagination

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

class UpdateUserById(generics.UpdateAPIView, UpdateModelMixin):
    queryset = User.objects.filter(is_admin=False, is_staff=False)
    serializer_class = AdminUserUpdateSerializer
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)

class ContactAdminView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        superuser = User.objects.filter(is_superuser=True, is_staff=True)
        if not superuser.exists():
            return Response(
                data={"message": _(UserConstantsMessage.ADMIN_CREDENTIALS_NOT_FOUND)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        description = f"{request.data.get('description')} \n \n From : {request.data.get('email')}"
        send_admin_mail(
            request.data.get("subject"),
            description,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email for user in superuser],
        )
        return Response(
            data={"message": _(UserConstantsMessage.DEFAULT_MAIL_SUCCESS)},
            status=status.HTTP_200_OK,
        )


# urls.py
from django.urls import path
path("admin/users/", UserView.as_view(), name="users"),
path(
    "admin/user/<int:pk>/",
    RetrieveDestroyUserById.as_view(),
    name="retrieve-delete-user",
),
path("admin/user/update/<int:pk>/", UpdateUserById.as_view(), name="update-user"),
path("admin/contact/", ContactAdminView.as_view(), name="contact-admin"),