async def publish_email_task(email_data: dict):
    from app.workers.task_email import send_welcome_email

    send_welcome_email.delay(email_data)
