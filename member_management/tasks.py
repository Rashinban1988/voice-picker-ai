from celery import shared_task
from django.db import transaction
from django.utils import timezone
import stripe
import logging

from member_management.models import Subscription, SubscriptionPlan, Organization

api_logger = logging.getLogger('django')

@shared_task
def fulfill_subscription_task(session_id, org_id, plan_id, customer_id, subscription_id):
    try:
        with transaction.atomic():
            organization = Organization.objects.get(id=org_id)
            plan = SubscriptionPlan.objects.get(id=plan_id)

            subscription, created = Subscription.objects.get_or_create(
                organization=organization,
                defaults={
                    'plan': plan,
                    'status': Subscription.Status.ACTIVE,
                    'stripe_customer_id': customer_id,
                    'stripe_subscription_id': subscription_id
                }
            )

            if created:
                api_logger.info(f"New subscription created for organization {organization.id} with plan {plan.id}")
            else:
                api_logger.info(f"Existing subscription found for organization {organization.id}. Current plan: {subscription.plan.id if subscription.plan else 'None'}")
                subscription.plan = plan
                subscription.status = Subscription.Status.ACTIVE
                subscription.stripe_subscription_id = subscription_id
                subscription.save()
                api_logger.info(f"Existing subscription updated to plan {subscription.plan.id}")

            stripe_subscription = stripe.Subscription.retrieve(subscription_id)

            subscription.current_period_start = timezone.datetime.fromtimestamp(
                stripe_subscription.current_period_start
            )
            subscription.current_period_end = timezone.datetime.fromtimestamp(
                stripe_subscription.current_period_end
            )
            subscription.save()

    except (Organization.DoesNotExist, SubscriptionPlan.DoesNotExist) as e:
        api_logger.error(f"Error processing subscription fulfillment: {e}")
        raise
    except Exception as e:
        api_logger.error(f"Unexpected error in fulfill_subscription_task: {e}")
        raise

@shared_task
def update_subscription_task(stripe_subscription_data):
    try:
        # まずstripe_subscription_idで検索（既存レコード用）
        subscription = Subscription.objects.filter(
            stripe_subscription_id=stripe_subscription_data['id']
        ).first()

        # stripe_subscription_idが未登録の場合はstripe_customer_idで検索
        if not subscription:
            subscription = Subscription.objects.filter(
                stripe_customer_id=stripe_subscription_data['customer']
            ).first()

        if not subscription:
            api_logger.error(f"Subscription not found for Stripe subscription ID: {stripe_subscription_data['id']} or customer ID: {stripe_subscription_data['customer']}")
            raise Subscription.DoesNotExist(f"Subscription not found for Stripe subscription ID: {stripe_subscription_data['id']} or customer ID: {stripe_subscription_data['customer']}")

        # サブスクリプションIDを必ず更新
        subscription.stripe_subscription_id = stripe_subscription_data['id']

        # プラン情報の更新
        if stripe_subscription_data.get('plan') and stripe_subscription_data['plan'].get('id'):
            try:
                stripe_price_id = stripe_subscription_data['plan']['id']
                plan = SubscriptionPlan.objects.get(stripe_price_id=stripe_price_id)
                subscription.plan = plan
                api_logger.info(f"Subscription plan updated to {plan.id} for subscription {subscription.id}")
            except SubscriptionPlan.DoesNotExist:
                api_logger.error(f"SubscriptionPlan with stripe_price_id {stripe_price_id} not found.")
        else:
            api_logger.warning(f"No plan information found in stripe_subscription object for subscription {subscription.id}")

        # ステータス更新
        if stripe_subscription_data['status'] == 'active':
            subscription.status = Subscription.Status.ACTIVE
        elif stripe_subscription_data['status'] == 'past_due':
            subscription.status = Subscription.Status.PAST_DUE
        elif stripe_subscription_data['status'] == 'canceled':
            subscription.status = Subscription.Status.CANCELED
        elif stripe_subscription_data['status'] == 'trialing':
            subscription.status = Subscription.Status.TRIAL
        else:
            subscription.status = Subscription.Status.INACTIVE

        # 期間情報も更新
        subscription.current_period_start = timezone.datetime.fromtimestamp(
            stripe_subscription_data['current_period_start']
        )
        subscription.current_period_end = timezone.datetime.fromtimestamp(
            stripe_subscription_data['current_period_end']
        )
        subscription.cancel_at_period_end = stripe_subscription_data.get('cancel_at_period_end', False)
        subscription.save()

    except Exception as e:
        api_logger.error(f"Error updating subscription: {e}")
        raise

@shared_task
def cancel_subscription_task(stripe_subscription_id):
    """サブスクリプション削除時の処理"""
    try:
        subscription = Subscription.objects.get(
            stripe_subscription_id=stripe_subscription_id
        )
        subscription.status = Subscription.Status.CANCELED
        subscription.save()

    except Subscription.DoesNotExist as e:
        api_logger.error(f"Subscription not found for Stripe subscription ID: {stripe_subscription_id}")
        raise e
    except Exception as e:
        api_logger.error(f"Unexpected error in cancel_subscription_task: {e}")
        raise