from django.core.management.base import BaseCommand
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Clears the application cache'

    def handle(self, *args, **kwargs):
        cache.clear()
        self.stdout.write('Cache has been cleared!')