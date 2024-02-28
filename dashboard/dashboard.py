# models.py
from django.db import models
from django.contrib.auth import get_user_model
from django_extensions.db.models import ActivatorModel, TimeStampedModel

User = get_user_model()

class DashboardProgress(ActivatorModel, TimeStampedModel):
    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="progress",
        verbose_name="User",
    )
    week_start_date = models.DateField(blank=True, null=True)
    week_end_date = models.DateField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "DashboardProgress"

# serializers.py
from rest_framework import serializers

class DashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardProgress
        fields = ["id", "user", "week_start_date", "week_end_date", "data"]

# pagination.py
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000


# func.py
from datetime import datetime, timedelta

import pytz
from django.conf import settings
from django.db.models import Sum

from course.models import TopicProgress

WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

DEFAULT_WEEKDAYS = {
    "Monday": 0,
    "Tuesday": 0,
    "Wednesday": 0,
    "Thursday": 0,
    "Friday": 0,
    "Saturday": 0,
    "Sunday": 0,
}

def dashboard_progress(user: object, instance=None, total_topic_progress=0) -> None:
    """
    Function to count user's weekly progress based on answers submitted.

    params:
        user: object: User object.
        obj: None
        total_topic_progress: int: default 0

    return:
        None
    """
    today = datetime.now(pytz.timezone(settings.TIME_ZONE)).weekday()
    queryset = TopicProgress.objects.filter(
        user=user,
    )

    total_progress = queryset.aggregate(Sum("progress")).get("progress__sum")

    week_start = datetime.now(pytz.timezone(settings.TIME_ZONE)) - timedelta(days=today)
    week_end = week_start + timedelta(days=6)

    if total_progress:
        total_topic_progress = int(total_progress / queryset.count())

    dash_queryset = DashboardProgress.objects.filter(
        user=user, week_start_date=week_start.date(), week_end_date=week_end.date()
    )

    if dash_queryset.exists():
        instance = dash_queryset.first()
        instance.data[f"{WEEKDAYS[today]}"] = total_topic_progress
        instance.save()
    else:
        instance = DashboardProgress.objects.create(
            week_start_date=week_start.date(),
            week_end_date=week_end.date(),
            user=user,
            data=DEFAULT_WEEKDAYS,
        )
    return instance

# views.py
from django.conf import settings
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

class DashboardProgressView(ListAPIView):
    queryset = DashboardProgress.objects.all()
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def list(self, request, *args, **kwargs):
        # create graph data
        instance = dashboard_progress(request.user)

        serializer = DashboardSerializer(instance)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)
