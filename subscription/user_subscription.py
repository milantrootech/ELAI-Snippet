# models.py
from django.apps import apps
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import ActivatorModel, TimeStampedModel

User = get_user_model()

class UserSubscriptionManager(models.Manager):
    def get_subscription(self, user: object):
        UserSubscription = apps.get_model("subscription", "UserSubscription")
        return UserSubscription.objects.select_related("plan").filter(
            user=user, status=UserSubscription.ActivationStatus.Activated
        )

class Subscription(ActivatorModel, TimeStampedModel):
    plan_name = models.CharField(
        _("Plan Name"), max_length=255, blank=False, null=False
    )
    membership_level = models.CharField(
        _("Membership Level"), default="", max_length=24
    )
    duration = models.IntegerField(_("Duration In Month"), default=0)
    price = models.DecimalField(
        _("Price"), max_digits=8, decimal_places=2, default=Decimal("0.00")
    )
    stripe_price_id = models.CharField(
        _("Stripe PriceID"), max_length=255, blank=True, null=True
    )
    stripe_product_id = models.CharField(
        _("Stripe ProductID"), max_length=255, blank=True, null=True
    )
    description = models.JSONField(blank=True, null=True)
    unlock_chat_feature = models.BooleanField(_("Unlock Chat Feature"), default=False)
    order = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")

    def __str__(self):
        return self.plan_name


class TransactionHistory(TimeStampedModel):
    user = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.CASCADE, related_name="user"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription",
    )
    checkout_session_id = models.CharField(
        _("Checkout Session ID"), max_length=255, null=True
    )
    charge_id = models.CharField(_("Charge ID"), max_length=255, null=True)
    customer_id = models.CharField(_("Customer ID"), max_length=255, null=True)
    stripe_subscription_id = models.CharField(
        _("Stripe Subscription ID"), max_length=255, null=True
    )
    payment_link = models.TextField(_("Payment Link ID"), null=True)
    price_id = models.CharField(_("Price ID"), max_length=255, null=True)
    product_id = models.CharField(_("Product ID"), max_length=255, null=True)
    data = models.JSONField(null=True, blank=True)
    is_subscribed = models.BooleanField(_("Subscribed"), default=False)
    auto_renew = models.BooleanField(_("Auto Renew"), default=False)

    class Meta:
        verbose_name = _("Transaction History")
        verbose_name_plural = _("Transaction History")

    def __str__(self):
        return self.checkout_session_id


class WebhookResponse(TimeStampedModel):
    data = models.JSONField()

    class Meta:
        verbose_name = _("Webhook Response")
        verbose_name_plural = _("Webhook Response")


class UserSubscription(ActivatorModel, TimeStampedModel):
    class ActivationStatus(models.TextChoices):
        Activated = "activated", _("Activated")
        Expired = "expired", _("Expired")
        Cancelled = "cancelled", _("Cancelled")

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_subscription",
    )
    plan = models.ForeignKey(
        Subscription,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="plan",
    )
    status = models.CharField(
        choices=ActivationStatus.choices,
        default=ActivationStatus.Expired,
        max_length=15,
    )

    objects = UserSubscriptionManager()

    class Meta:
        verbose_name = _("User Subscription")
        verbose_name_plural = _("User Subscriptions")

    def __str__(self):
        return self.user.email

# utils.py
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification

from dashboard.dashboard import DashboardProgress
from course.models import TopicProgress, Result

lifetime_duration = 0

def create_product_and_price(data, instance=None, product=None):
    """
    A function to create product and price in stripe.
    """
    if not instance:
        product = stripe.Product.create(name=data.get("plan_name"))
    stripe_product_id = instance.stripe_product_id if instance else product.get("id")
    sub_price = data.get("price")
    duration = data.get("duration")

    if duration == lifetime_duration:
        price = stripe.Price.create(
            unit_amount=int(Decimal(sub_price)) * 100,
            currency="aed",
            product=stripe_product_id,
        )
    else:
        price = stripe.Price.create(
            unit_amount=int(Decimal(sub_price)) * 100,
            currency="aed",
            product=stripe_product_id,
            recurring={"interval": "month", "interval_count": duration},
        )
    return stripe_product_id, price.get("id")

def create_payment_link(subscription: object, user: object, mode: str):
    """
    Dynamic

     product link will be created.

    params:
        subscription: object: model object
        user: object: model object
    """
    try:
        customer = stripe.Customer.create(email=user.email)
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": subscription.stripe_price_id,
                    "quantity": 1,
                },
            ],
            mode=mode,
            success_url=settings.SUCCESS_URL,
            cancel_url=settings.CANCEL_URL,
            customer=customer,
            metadata={"user_email": user.email, "user_id": user.id},
        )
        return session.url
    except stripe.error.StripeError as e:
        raise Exception("Stripe error: " + str(e))

def create_subscription_notification(
    recipient: object, model: str, custom_notification: str
):
    """
    A function to crate notification for subscription model.

    params:
        recipient: object: user object
        model: str: model name
        custom_notification: str: message to display

    return:

    """
    content_type = ContentType.objects.get(app_label=model, model=model)
    Notification.objects.create(
        level=Notification.LEVELS.success,
        recipient=recipient,
        actor_content_type=content_type,
        actor_object_id=content_type.id,
        verb=custom_notification,
    )
    return SubscriptionConstantsMessage.NOTIFICATION_SUCCESS


def create_transaction_data(user: object, subscription: object, session: dict) -> bool:
    """
    create transaction based on event data

    params:
        user: object: User object
        subscription: object: Subscription model object
        session: dict: checkout session dict
    """
    charge = None
    if session["payment_intent"]:
        payment_intent = stripe.PaymentIntent.retrieve(session["payment_intent"])
        charge = stripe.Charge.retrieve(payment_intent["latest_charge"])
    transaction_data = {
        "user": user,
        "subscription": subscription,
        "price_id": subscription.stripe_price_id,
        "checkout_session_id": session["id"],
        "charge_id": charge.id if charge else None,
        "data": session,
        "customer_id": session["customer"],
        "stripe_subscription_id": session["subscription"],
    }
    transaction_data = TransactionHistory(**transaction_data)
    transaction_data.save()
    return True

def remove_subscription_data(user: object) -> None:
    """
    A function to remove user submitted data when subscription cancels or expires.

    params:
        user: object: A user instance.

    return:
        None
    """
    TopicProgress.objects.filter(user=user).delete()
    Result.objects.filter(user=user).delete()
    DashboardProgress.objects.filter(user=user).delete()
    return None

def transaction_history_data(history_data: dict) -> dict:
    """
    Function to prepare transaction history data

    params:
        history_data: dict: Transaction history data

    return:
        data: dict: custom fields dictionary with transaction data
    """
    data = {
        "id": history_data.get("id"),
        "currency": history_data.get("currency"),
        "amount": float(history_data.get("amount_total") / 100),
        "metadata": history_data.get("metadata"),
    }
    return data

def cancel_subscription(transaction_data_objs: object):
    """
    create cancel subscription notification

    params:
        transaction_data_objs: object: Transacrion History object

    """
    if transaction_data_objs.exists():
        transaction_data = transaction_data_objs.first()
        transaction_data.is_subscribed = False
        transaction_data.save()

        user_subscription_objs = UserSubscription.objects.filter(
            user=transaction_data.user,
            status=UserSubscription.ActivationStatus.Activated,
        )
        if user_subscription_objs.exists():
            user_subscription_data = user_subscription_objs.first()
            user_subscription_data.status = UserSubscription.ActivationStatus.Cancelled
            user_subscription_data.save()
            create_subscription_notification(
                transaction_data.user,
                "subscription",
                SubscriptionConstantsMessage.SUBSCRIPTION_CANCELED,
            )

def webhook_event_data(event: dict, data: dict):
    """
    Handles webhook events triggered from stripe
    and creates transaction record in db.

    params:
        event: dict: event dict receive from webhook
        data: dict: session data dictionary
    """
    event_type = event["type"]
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        email = data["data"]["object"]["metadata"]["user_email"]
        user = User.objects.get(email=email)
        price = data["data"]["object"]["amount_total"]
        checkout_session_line_item = stripe.checkout.Session.list_line_items(
            session["id"], limit=1
        )
        price_id = checkout_session_line_item["data"][0]["price"]["id"]
        queryset = Subscription.objects.filter(
            stripe_price_id=price_id, price=Decimal(int(price) / 100)
        )
        if not queryset.exists():
            return

        subscription = queryset.first()
        create_transaction_data(user, subscription, session)
        transaction_data_objs = TransactionHistory.objects.filter(
            checkout_session_id=session["id"]
        )
        if transaction_data_objs.exists():
            subscription_data = transaction_data_objs.first()
            subscription_data.is_subscribed = True
            subscription_data.save()

        user_subscription_objs = UserSubscription.objects.filter(
            user=user, plan=subscription
        )
        if user_subscription_objs.exists():
            user_subscription = user_subscription_objs.first()
            subscription_purchase_timestamp = session["created"]
            user_subscription.activate_date = datetime.fromtimestamp(
                subscription_purchase_timestamp
            )
            user_subscription.deactivate_date = datetime.fromtimestamp(
                subscription_purchase_timestamp
            ) + relativedelta(months=user_subscription.plan.duration)
            user_subscription.save()

        create_subscription_notification(
            user, "subscription", SubscriptionConstantsMessage.SUBSCRIPTION_CREATED
        )

    if event_type == "charge.refunded":
        session = event["data"]["object"]
        transaction_data_objs = TransactionHistory.objects.filter(
            charge_id=session["id"]
        )
        cancel_subscription(transaction_data_objs)

    if event_type == "customer.subscription.deleted":
        session = event["data"]["object"]
        transaction_data_objs = TransactionHistory.objects.filter(
            stripe_subscription_id=session["id"], customer_id=session["customer"]
        )

        cancel_subscription(transaction_data_objs)
    return True


# serializers.py
import stripe
from decimal import Decimal

from rest_framework import serializers

class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan_name",
            "membership_level",
            "duration",
            "price",
            "stripe_price_id",
            "stripe_product_id",
            "description",
            "unlock_chat_feature",
            "order",
        ]

    def validate_description(self, obj):
        if obj.get("value"):
            return obj
        else:
            raise serializers.ValidationError("Description must be a valid JSON.")

    def update(self, instance, validated_data):
        membership_level = validated_data.get("membership_level")

        # Check if a Subscription with the same membership level already exists
        if instance.membership_level != membership_level:
            if Subscription.objects.filter(membership_level=membership_level).exists():
                raise serializers.ValidationError(
                    f"Subscription with membership level {membership_level} already exists."
                )

        if Decimal(instance.price) != Decimal(validated_data.get("price")):
            product_id, price_id = create_product_and_price(validated_data, instance)
            # modify stripe price
            stripe.Price.modify(
                price_id,
            )
            instance.stripe_price_id = price_id
        instance.membership_level = (
            membership_level if membership_level else instance.membership_level
        )
        instance.price = validated_data.get("price")
        instance.duration = validated_data.get("duration")
        instance.description = validated_data.get("description", instance.description)
        instance.unlock_chat_feature = validated_data.get("unlock_chat_feature")
        instance.order = validated_data.get("order", instance.order)
        instance.save()
        return instance


class TransactionHistorySerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer()
    user = UserResponseSerializer()
    payment_method_types = serializers.SerializerMethodField()

    class Meta:
        model = TransactionHistory
        fields = [
            "id",
            "created",
            "user",
            "subscription",
            "payment_method_types",
            "is_subscribed",
        ]

    def get_payment_method_types(self, obj):
        if obj and obj.data:
            payment_method_types = obj.data.get("payment_method_types", [])
            return payment_method_types
        return []


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionSerializer()
    user = UserResponseSerializer()

    class Meta:
        model = UserSubscription
        fields = ["id", "user", "plan", "status"]

# pagination.py
from rest_framework.pagination import PageNumberPagination
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000

# constants.py
class GeneralConstantsMessage:
    BLANK_FIELD_MESSAGE = "This field cannot be blank."
    FIELD_CANNOT_BE_NULL_ERROR_MESSAGE = "This field cannot be null."
    INVALID_CREDENTIAL = "Invalid Credentials!"
    DATE_FORMAT_ERROR = (
        "Date has wrong format. Use one of these formats instead: YYYY-MM-DD."
    )
    EMAIL_REQUIRED_ERROR = "Email address required!"
    ENTER_VALID_EMAIL = "Enter a valid email address."
    PASSWORD_MISMATCH_ERROR = "Password fields didn't match."
    PASSWORD_TOO_SHORT_ERROR = (
        "This password is too short. It must contain at least 8 characters."
    )
    PASSWORD_ENTIRELY_NUMERIC_ERROR = "This password is entirely numeric."
    PASSWORD_TOO_COMMON_ERROR = "This password is too common."
    UNREAD_FIELD_REQUIRED = "The unread field is required."
    PROVIDED_VALUE_ALREADY_EXISTS = (
        "Provided value already exists for different subscription!"
    )
    SUBSCRIPTION_ID_REQUIRED = "Subscription ID is required!"
    SUBSCRIPTION_NOT_FOUND = "Subscription not found!"
    STRIPE_SIGNATURE_MISSING = "Stripe signature missing"
    INVALID_STRIPE_SIGNATURE = "Invalid Stripe signature"
    USER_ALREADY_EXISTS = "User Already Exists!"
    AUTHENTICATION_CREDENTIALS_NOT_PROVIDED = (
        "Authentication credentials were not provided."
    )
    NOT_FOUND = "Not found."
    
class SubscriptionConstantsMessage:
    NOTIFICATION_SUCCESS = "Subscription notification created successfully!"
    PRODUCT_CREATE_SUCCESS = "Product and Price created successfully!"
    PAYMENT_LINK_SUCCESS = "Payment link generated successfully!"
    PAYMENT_LINK_FAILED = "Failed to generate Payment link!"
    SUBSCRIPTION_CREATED = "Subscription created successfully!"
    SUBSCRIPTION_CREATE_FAILED = "Failed to create subscription!"
    SUBSCRIPTION_CANCELED = "Subscription canceled successfully"
    TRANSACTION_CREATED = "Transaction data created successfully!"
    TRANSACTION_CREATE_FAILED = "Failed to create subscription transaction data!"
    USER_SUBSCRIPTION_CREATED = "UserSubscription created successfully!"
    USER_SUBSCRIPTION_NOT_EXIST = "User subscription does not exists!"
    USER_SUBSCRIPTION_CREATE_FAILED = "Failed to create subscription transaction data!"
    SUBSCRIPTION_ID_REQUIRED = "Subscription ID is required!"
    USER_DONT_HAVE_ACTIVE_SUBSCRIPTION = "User with active subscription not found!"
    USER_NOT_SUBSCRIBED = "User is not subscribed with any of the subscription plan."
    USER_ALREADY_SUBSCRIBED = "User is already subscribed with subscription plan!"
    ACTIVE_USER_WITH_SUBSCRIPTION_NOT_FOUND = (
        "User not found with active subscription plan."
    )
    TRANSACTION_HISTORY_NOT_FOUND = "Transaction history not found for this user"
    SUBSCRIPTION_CHANGE_TO_AUTO_RENEW = (
        "Subscription changes to auto renewal successfully."
    )
    AUTO_RENEW_SUBSCRIPTION_UNABLE = "Subscription auto renewal unable successfully."

# views.py
import json
from datetime import datetime

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stripe.error import StripeError, SignatureVerificationError

class SubscriptionView(generics.ListAPIView):
    queryset = Subscription.objects.all().order_by("order")
    serializer_class = SubscriptionSerializer
    permission_classes = (AllowAny,)
    pagination_class = StandardResultsSetPagination


class SubscriptionCreateView(generics.CreateAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        data = request.data
        if Subscription.objects.filter(order=data.get("order")).exists():
            return Response(
                {"message": GeneralConstantsMessage.PROVIDED_VALUE_ALREADY_EXISTS},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product_id, price_id = create_product_and_price(data)
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            serializer.save(stripe_price_id=price_id, stripe_product_id=product_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except StripeError as e:
            return Response({"message": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionRetrieveUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = (IsAuthenticated,)


class CreatePaymentLinkView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        subscription_id = request.data.get("subscription_id")
        user = self.request.user

        if not subscription_id:
            return Response(
                {"message": GeneralConstantsMessage.SUBSCRIPTION_ID_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return Response(
                {"message": GeneralConstantsMessage.SUBSCRIPTION_NOT_FOUND},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activation_status = UserSubscription.objects.filter(
            user=user, status=UserSubscription.ActivationStatus.Activated
        )

        if activation_status.exists():
            return Response(
                {"message": SubscriptionConstantsMessage.USER_ALREADY_SUBSCRIBED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if subscription.duration == lifetime_duration:
                payment_link = create_payment_link(subscription, user, "payment")
            else:
                payment_link = create_payment_link(subscription, user, "subscription")
            return Response(
                {"payment_link": payment_link}, status=status.HTTP_201_CREATED
            )
        except StripeError as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SubscriptionWebhook(APIView):
    permission_classes = (AllowAny,)

    @csrf_exempt
    def post(self, request):
        stripe.api_key = settings.STRIPE_API_KEY
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", None)
        request_json = request.body.decode("utf-8")
        data = json.loads(request_json)
        WebhookResponse.objects.create(data=data)

        if not sig_header:
            return Response(
                {"error": GeneralConstantsMessage.STRIPE_SIGNATURE_MISSING},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event = stripe.Webhook.construct_event(
                request.body, sig_header, endpoint_secret
            )
        except SignatureVerificationError:
            return Response(
                {"error": GeneralConstantsMessage.INVALID_STRIPE_SIGNATURE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        webhook_event_data(event, data)
        return Response({"success": True}, status=status.HTTP_200_OK)


class TransactionHistoryDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {}
        user = self.request.user
        transaction_history = (
            TransactionHistory.objects.filter(user=user).order_by("-created").first()
        )
        if transaction_history:
            history_data = transaction_history.data
            data = transaction_history_data(history_data)
        return Response(data, status=status.HTTP_200_OK)


class SubscribedUserList(generics.ListAPIView):
    queryset = (
        TransactionHistory.objects.filter(is_subscribed=True).all().order_by("-created")
    )
    serializer_class = TransactionHistorySerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]


class ActivatedSubscribeUserList(generics.ListAPIView):
    queryset = UserSubscription.objects.filter(
        status=UserSubscription.ActivationStatus.Activated
    ).all()
    serializer_class = UserSubscriptionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]


class UserTransactionHistoryDetail(generics.ListAPIView):
    queryset = TransactionHistory.objects.all()
    serializer_class = TransactionHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by("-id")


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user

        transaction_history_objs = TransactionHistory.objects.filter(
            user=user, is_subscribed=True
        )

        if not transaction_history_objs.exists():
            return Response(
                {"message": SubscriptionConstantsMessage.TRANSACTION_HISTORY_NOT_FOUND},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subsription_plan = transaction_history_objs.first()
        user_subscription_objs = UserSubscription.objects.filter(
            user=user,
            plan=subsription_plan.subscription,
            status=UserSubscription.ActivationStatus.Activated,
        )

        if not user_subscription_objs.exists():
            return Response(
                {
                    "message": SubscriptionConstantsMessage.ACTIVE_USER_WITH_SUBSCRIPTION_NOT_FOUND
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_subscription_data = user_subscription_objs.first()
        activate_date = user_subscription_data.activate_date.date()
        today_date = datetime.now().date()
        difference = today_date - activate_date
        success_message = SubscriptionConstantsMessage.SUBSCRIPTION_CANCELED

        if difference.days > int(settings.REFUND_PERIOD):
            subsription_plan.is_subscribed = False
            subsription_plan.save()

            user_subscription_data.status = UserSubscription.ActivationStatus.Cancelled
            user_subscription_data.save()

            create_subscription_notification(
                subsription_plan.user,
                "subscription",
                success_message,
            )
        else:
            try:
                if subsription_plan.subscription.duration == lifetime_duration:
                    charge = stripe.Charge.retrieve(subsription_plan.charge_id)
                    stripe.Refund.create(charge=charge.id)
                else:
                    stripe.Subscription.delete(subsription_plan.stripe_subscription_id)
            except stripe.error.StripeError as e:
                return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

        remove_subscription_data(user)

        return Response(
            {"message": success_message},
            status=status.HTTP_200_OK,
        )


class AutoRenewalSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        auto_renew = request.data.get("auto_renew")

        transaction_history_objs = TransactionHistory.objects.filter(
            user=request.user, is_subscribed=True
        )
        if not transaction_history_objs.exists():
            return Response(
                {"message": SubscriptionConstantsMessage.TRANSACTION_HISTORY_NOT_FOUND},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_history_data = transaction_history_objs.first()
        payment_intent_id = transaction_history_data.data["payment_intent"]

        # Retrieve the PaymentIntent
        stripe_payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        payment_method_id = stripe_payment_intent["payment_method"]

        # Attach PaymentMethod to Customer
        try:
            if not stripe_payment_intent["customer"]:
                stripe.PaymentMethod.attach(
                    payment_method_id,
                    customer=transaction_history_data.customer_id,
                )
        except stripe.error.StripeError as e:
            return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if auto_renew:
                stripe.SetupIntent.create(
                    customer=transaction_history_data.customer_id,
                    automatic_payment_methods={
                        "enabled": auto_renew,
                    },
                )
                success_message = (
                    SubscriptionConstantsMessage.SUBSCRIPTION_CHANGE_TO_AUTO_RENEW
                )
            else:
                stripe.SetupIntent.create(
                    customer=transaction_history_data.customer_id,
                    payment_method_types=transaction_history_data.data[
                        "payment_method_types"
                    ],
                    automatic_payment_methods={
                        "enabled": auto_renew,
                    },
                )
                success_message = (
                    SubscriptionConstantsMessage.AUTO_RENEW_SUBSCRIPTION_UNABLE
                )

            transaction_history_data.auto_renewal = auto_renew
            transaction_history_data.save()
        except stripe.error.StripeError as e:
            return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": success_message}, status=status.HTTP_200_OK)


# utils.py
from django.urls import path
    
path("plans/", SubscriptionView.as_view(), name="subscriptions-list"),
path("admin/plan/", SubscriptionCreateView.as_view(), name="subscription-create"),
path(
    "admin/plan/<int:pk>/",
    SubscriptionRetrieveUpdateDeleteView.as_view(),
    name="subscription-retrieve-update-delete",
),
path(
    "admin/subscribed/users/",
    SubscribedUserList.as_view(),
    name="subscribed-user-list",
),
path(
    "create-payment-link/",
    CreatePaymentLinkView.as_view(),
    name="create-payment-link",
),
path("webhook/", SubscriptionWebhook.as_view(), name="subscription-webhook"),
path(
    "transaction-detail/",
    TransactionHistoryDetail.as_view(),
    name="transaction-detail",
),
path(
    "active-subscription-list/",
    ActivatedSubscribeUserList.as_view(),
    name="active-subscription-list",
),
path(
    "user-transaction-detail/",
    UserTransactionHistoryDetail.as_view(),
    name="user-transaction-detail",
),
path(
    "cancel-subscription/",
    CancelSubscriptionView.as_view(),
    name="cancel-subscription",
),
path(
    "auto-renew/",
    AutoRenewalSubscriptionView.as_view(),
    name="auto-renewal-subscription",
),