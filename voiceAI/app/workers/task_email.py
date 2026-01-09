import json
from voiceAI.voiceAI import settings
from django.core.mail import send_mail
from app.common.rabbit_mq import channel

def callback(ch, method, properties, body):
    data = json.loads(body)
    to_email = data.get("to_email")
    subject = data.get("subject", "No Subject")
    context = data.get("context", {})

    message = f"Hello {context.get('username')}, welcome to VoiceAI!"

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
    )

    print(f"Email sent to {to_email}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue="email_tasks", on_message_callback=callback)

print(" [*] Waiting for email tasks. To exit press CTRL+C")
channel.start_consuming()