from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files import File
from django.core.management.base import BaseCommand

from demo.models import Supplier, Request, Attachment, Settings
from demo.permissions import MANAGERS, USERS

SAMPLE_FILES_DIR = Path(__file__).resolve().parent.parent.parent / 'fixtures' / 'sample_files'


class Command(BaseCommand):
    help = 'Populate the demo project with sample suppliers, requests, attachments and settings.'

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin')
            self.stdout.write(self.style.SUCCESS('Created superuser admin/admin'))

        managers_group, _ = Group.objects.get_or_create(name=MANAGERS)
        users_group, _ = Group.objects.get_or_create(name=USERS)

        for username, group in [('manager', managers_group), ('user', users_group)]:
            if not User.objects.filter(username=username).exists():
                account = User.objects.create_user(username, f'{username}@example.com', username)
                account.groups.add(group)
                self.stdout.write(self.style.SUCCESS(f'Created user {username}/{username} ({group.name})'))

        suppliers = {}
        for name, tax_code in [
            ('Acme Inc', 'AC1234567890'),
            ('Beta Corp', 'BC0987654321'),
            ('Gamma & Co', 'GC5566778899'),
            ('Delta LLC', 'DL1122334455'),
            ('John Smith', 'JS9988776655'),
        ]:
            supplier, _ = Supplier.objects.get_or_create(
                company_name=name, defaults={'tax_code': tax_code, 'active': True},
            )
            suppliers[name] = supplier

        cert_path = SAMPLE_FILES_DIR / 'sample-certification.pdf'
        acme = suppliers['Acme Inc']
        if not acme.certification:
            with open(cert_path, 'rb') as fh:
                acme.certification.save('certification.pdf', File(fh), save=True)

        requests_data = [
            ('New laptops for the design team', 'draft', '4200.00', suppliers['Acme Inc']),
            ('Office chairs replacement', 'submitted', '1800.00', suppliers['Beta Corp']),
            ('Annual software licenses', 'approved', '9600.00', suppliers['Gamma & Co']),
            ('Marketing materials reprint', 'rejected', '650.00', suppliers['Delta LLC']),
            ('Unassigned budget request', 'draft', '500.00', None),
        ]
        requests = {}
        for title, status, budget, supplier in requests_data:
            req, _ = Request.objects.get_or_create(
                title=title,
                defaults={
                    'description': f'Sample request: {title.lower()}.',
                    'budget': budget,
                    'status': status,
                    'supplier': supplier,
                },
            )
            requests[title] = req

        laptops_request = requests['New laptops for the design team']
        if not laptops_request.attachments.exists():
            spec_path = SAMPLE_FILES_DIR / 'sample-spec.txt'
            attachment = Attachment(request=laptops_request, description='Vendor quote')
            with open(spec_path, 'rb') as fh:
                attachment.file.save('quote.txt', File(fh), save=True)

        Settings.objects.get_or_create(
            pk=1, defaults={'auto_approval_threshold': '1000.00', 'notification_email': 'purchasing@example.com'},
        )

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
