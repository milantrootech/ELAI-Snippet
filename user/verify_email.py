# views.py
from django.utils.translation import gettext_lazy as _
from rest_framework import views, status
from rest_framework.response import Response

from django.contrib.auth import get_user_model
User = get_user_model()

class GeneralConstantsMessage:
    EMAIL_REQUIRED_ERROR = "Email address required!"
    USER_ALREADY_EXISTS = "User Already Exists!"
    
class UserConstantsMessage:
    EMAIL_IS_NOT_AVAILABLE_TO_CREATE_USER = (
        "This email is available to register a new user."
    )

class VerifyEmailView(views.APIView):
    def post(self, request):
        if not request.data.get("email"):
            return Response(
                {"message": GeneralConstantsMessage.EMAIL_REQUIRED_ERROR},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email=request.data.get("email").lower())

        if user.exists() and user.first().is_verified:
            return Response(
                {"message": GeneralConstantsMessage.USER_ALREADY_EXISTS},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": UserConstantsMessage.EMAIL_IS_NOT_AVAILABLE_TO_CREATE_USER,
                "data": request.data,
            },
            status=status.HTTP_200_OK,
        )

# urls.py
from django.urls import path
path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
