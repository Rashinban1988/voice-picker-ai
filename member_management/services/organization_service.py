from member_management.models import Organization
from member_management.schemas import OrganizationCreateData
class OrganizationService:
    @staticmethod
    def create_organization(org_data: OrganizationCreateData):
        return Organization.objects.create(
            name=org_data.name,
            phone_number=org_data.phone_number
        )

    @staticmethod
    def get_organization_queryset(user):
        if user.is_staff or user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=user.organization.id)