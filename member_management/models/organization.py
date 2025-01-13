from django.db import models
from django.utils import timezone
import uuid

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name='組織名')
    phone_number = models.CharField(max_length=15, verbose_name='電話番号')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    is_exist = models.BooleanField(default=True, verbose_name='存在')

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.is_exist = False
        self.save()

    def is_exist(self):
        return self.is_exist

    def add_user(self, user):
        user.organization = self
        user.save()

    def add_uploaded_file(self, uploaded_file):
        uploaded_file.organization = self
        uploaded_file.save()

    def users(self):
        from .user import User
        return User.objects.filter(organization=self)

    def uploaded_files(self):
        from voice_picker.models.uploaded_file import UploadedFile
        return UploadedFile.objects.filter(organization=self)

    def __str__(self):
        return f"Organization: {self.name}"

    class Meta:
        verbose_name = '組織'
        verbose_name_plural = '組織'