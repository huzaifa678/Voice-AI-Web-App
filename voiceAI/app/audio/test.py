import asyncio
import aio_pika
import json

async def test_publish_ws(user_id: str, message: str):
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
    channel = await connection.channel()

    exchange = await channel.declare_exchange(
        "audio_responses_exchange",
        aio_pika.ExchangeType.DIRECT,
        durable=True
    )

    payload = {
        "user_id": user_id,
        "response": message
    }

    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode()
        ),
        routing_key="audio_responses"
    )

    await channel.close()
    await connection.close()
    print(f"Published test message for user_id={user_id}")

asyncio.run(test_publish_ws("YOUR_TEST_USER_ID", "Hello from test!"))

