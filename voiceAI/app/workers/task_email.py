import os
from dotenv import load_dotenv
import django
from django.conf import settings
from django.core.mail import send_mail

from app.common.celery import celery_app

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")
django.setup()


@celery_app.task(name="app.workers.task_email.send_welcome_email", queue="email_tasks")
def send_welcome_email(email_data: dict):
    """Send a welcome email using Django's send_mail."""

    to_email = email_data.get("to_email")
    subject = email_data.get("subject", "No Subject")
    context = email_data.get("context", {})

    if not to_email:
        return

    message_body = f"""
Hello {context.get('username', 'User')},

Welcome to VoiceAI!

Thanks,
VoiceAI Team
""".strip()

    send_mail(
        subject,
        message_body,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False,
    )
