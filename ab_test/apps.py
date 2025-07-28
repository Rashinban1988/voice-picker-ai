from django.apps import AppConfig


class AbTestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ab_test'
    verbose_name = 'A/B Test'