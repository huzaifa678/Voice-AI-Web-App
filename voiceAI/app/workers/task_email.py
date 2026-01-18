import os
import json
import asyncio
from dotenv import load_dotenv
import aio_pika
import django

from app.common.rabbit_mq import get_connection

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voiceAI.settings")
django.setup()

from django.conf import settings
from django.core.mail import send_mail


async def handle_email_message(message: aio_pika.IncomingMessage):
    async with message.process(): 
        data = json.loads(message.body)

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

        await asyncio.to_thread(
            send_mail,
            subject,
            message_body,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            False,
        )

        print(f"Email sent to {to_email}", flush=True)


async def main():
    connection = await get_connection()
    channel = await connection.channel()

    queue = await channel.declare_queue(
        "email_tasks",
        durable=True,
    )

    await queue.consume(handle_email_message)

    print(" [*] Waiting for email tasks")
    print(" Press CTRL + C to exit")
    await asyncio.Future()  
