"""
Management command to permanently delete survey responses that have been in trash for 30+ days.
Run this command daily via cron job or scheduled task.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import SurveyResponse


class Command(BaseCommand):
    help = 'Permanently delete survey responses that have been in trash for 30+ days'

    def handle(self, *args, **options):
        # Calculate the date 30 days ago
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Find all responses deleted 30+ days ago
        old_responses = SurveyResponse.objects.filter(
            deleted_at__isnull=False,
            deleted_at__lte=cutoff_date
        )
        
        count = old_responses.count()
        
        if count > 0:
            # Permanently delete them
            old_responses.delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully permanently deleted {count} survey response(s) that were in trash for 30+ days.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('No responses found that need to be permanently deleted.')
            )

