from member_management.models import Organization, Subscription
from member_management.schemas import OrganizationCreateData
class OrganizationService:
    @staticmethod
    def create_organization(org_data: OrganizationCreateData):
        organization = Organization.objects.create(
            name=org_data.name,
            phone_number=org_data.phone_number
        )

        # 組織作成時にSubscriptionレコードも作成（初回登録なのでトライアル利用可能）
        Subscription.objects.create(
            organization=organization,
            status=Subscription.Status.INACTIVE,
            has_used_trial=False  # 初回登録時のみトライアル利用可能
        )

        return organization

    @staticmethod
    def get_organization_queryset(user):
        if user.is_staff or user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=user.organization.id)