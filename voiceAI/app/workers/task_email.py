import os
import asyncio
from celery import shared_task
from dotenv import load_dotenv
import django

from django.conf import settings
from django.core.mail import send_mail

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")
django.setup()


@shared_task(autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def handle_email_message(data: dict):
    """
    Celery task to send emails.
    data: dict containing 'to_email', 'subject', 'context'
    """
    to_email = data.get("to_email")
    subject = data.get("subject", "No Subject")
    context = data.get("context", {})

    if not to_email:
        print("No recipient email")
        return

    message_body = f"""
Hello {context.get('username', 'User')},

Welcome to VoiceAI!

Thanks,
VoiceAI Team
""".strip()

    asyncio.run(
        asyncio.to_thread(
            send_mail,
            subject,
            message_body,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            False
        )
    )

    print(f"Email sent to {to_email}", flush=True)
