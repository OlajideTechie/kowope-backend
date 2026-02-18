from django.http import JsonResponse
from django.db import connection
import time

def health_check(request):
    start = time.time()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    latency = (time.time() - start) * 1000

    return JsonResponse({
        "status": "ok",
        "db": "connected",
        "latency_ms": round(latency, 2)
    })