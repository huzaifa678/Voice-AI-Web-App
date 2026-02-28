from django.http import JsonResponse
import time

START_TIME = time.time()


def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "voice-ai",
            "uptime_sec": int(time.time() - START_TIME),
        }
    )
