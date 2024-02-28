# models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from subscription.user_subscription import Subscription
from django_extensions.db.models import ActivatorModel, TimeStampedModel
from django.contrib.auth import get_user_model

User = get_user_model()

class ProficiencyLevel(models.TextChoices):
    Beginner = "Beginner"
    Intermediate = "Intermediate"
    Advance = "Advance"

class Chapter(TimeStampedModel):
    name = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Chapter Name")
    )
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("Chapter")

class Topics(ActivatorModel):
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chapter_topics",
        verbose_name=_("Chapter"),
    )
    topic = models.CharField(max_length=200)
    level = models.CharField(
        choices=ProficiencyLevel.choices,
        null=True,
        blank=True,
        max_length=30,
        verbose_name=_("User Proficiency Level"),
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_topics",
        verbose_name=_("User Subscription"),
    )
    example_format = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Example Format")
    )
    # objects = TopicManager()

class TopicProgress(ActivatorModel, TimeStampedModel):
    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="topic_progress",
        verbose_name=_("User"),
    )
    topic = models.ForeignKey(
        Topics,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="topic_progress_topic",
        verbose_name=_("Topic"),
    )
    progress = models.IntegerField(_("Progress"), default=0)
    total_correct_answers = models.IntegerField(_("Total Correct Answers"), default=0)
    total_wrong_answers = models.IntegerField(_("Total Wrong Answers"), default=0)
    level = models.CharField(
        choices=ProficiencyLevel.choices,
        null=True,
        blank=True,
        max_length=30,
        verbose_name=_("User Proficiency Level"),
    )

    # objects = ProgressManager()

    def __str__(self):
        return self.topic.topic

    class Meta:
        verbose_name = _("Topic Progress")

# serializers.py
from rest_framework import serializers

class TopicProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicProgress
        fields = [
            "id",
            "user",
            "topic",
            "progress",
            "total_correct_answers",
            "total_wrong_answers",
            "level",
        ]

class TopicSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Topics
        fields = [
            "id",
            "chapter",
            "topic",
            "level",
            "subscription",
            "example_format",
            "progress",
        ]

    def get_progress(self, obj, topic_progress=None):
        if self.context.get("extra_fields"):
            progress_obj = TopicProgress.objects.filter(
                topic=obj, user=self.context.get("user")
            )

            if progress_obj.exists():
                topic_progress = progress_obj.first()

            serializer = TopicProgressSerializer(topic_progress)
            return serializer.data
        else:
            return None

class ChapterSerializer(serializers.ModelSerializer):
    topics = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Chapter
        fields = ["id", "name", "order", "topics"]

    def get_topics(self, obj):
        if self.context.get("extra_fields"):
            if self.context.get("lifetime_membership"):
                queryset = Topics.objects.get_ordered_topics(
                    self.context.get("level"), obj
                )
            else:
                queryset = Topics.objects.get_subscription_topics(
                    self.context.get("level"), obj, self.context.get("duration")
                )

            serializer = TopicSerializer(queryset, many=True, context=self.context)
            return serializer.data
        else:
            topics = Topics.objects.filter(chapter=obj).order_by("id")
            serializers = TopicSerializer(topics, many=True, context=self.context)
            return serializers.data

# pagination.py
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000

# views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

class AdminTopicsViewset(viewsets.ModelViewSet):
    queryset = Topics.objects.all()
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination


class AdminChaptersViewset(viewsets.ModelViewSet):
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

# urls.py
from rest_framework import routers
router = routers.SimpleRouter()

router.register(r"admin/topics", AdminTopicsViewset),
router.register(r"admin/chapters", AdminChaptersViewset),

