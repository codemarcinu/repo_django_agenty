from django.core.management.base import BaseCommand
from inventory.models import Receipt
from chatbot.tasks import orchestrate_receipt_processing

class Command(BaseCommand):
    help = 'Restarts the processing of a specific receipt by ID.'

    def add_arguments(self, parser):
        parser.add_argument('receipt_id', type=int, help='The ID of the receipt to restart processing for.')
    
    def handle(self, *args, **options):
        receipt_id = options['receipt_id']
        
        try:
            receipt = Receipt.objects.get(id=receipt_id)
            receipt.status = 'processing'
            receipt.save()
            
            # Uruchom ponownie orchestration
            orchestrate_receipt_processing.delay(receipt_id)
            
            self.stdout.write(self.style.SUCCESS(f"✅ Restart processing for receipt {receipt_id}"))
            
        except Receipt.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"❌ Receipt {receipt_id} not found"))