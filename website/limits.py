import os
import time
from datetime import datetime, timezone
from django.db import transaction
from django.utils.crypto import salted_hmac
from .models import RequestLimit

def allow_request(request, scope, limit, seconds=3600):
    address = request.META.get("REMOTE_ADDR", "unknown")
    # Enable only when Gunicorn is bound to localhost and Nginx replaces this header.
    if os.environ.get("DJANGO_TRUST_PROXY_IP") == "1":
        address = request.META.get("HTTP_X_REAL_IP", address)
    now = time.time()
    window = int(now // seconds)
    key = salted_hmac("request-limit", f"{scope}:{address}:{window}").hexdigest()
    expires = datetime.fromtimestamp((window + 1) * seconds, tz=timezone.utc)
    with transaction.atomic():
        RequestLimit.objects.get_or_create(key=key, defaults={"expires_at": expires})
        row = RequestLimit.objects.select_for_update().get(key=key)
        if row.count >= limit:
            return False
        row.count += 1
        row.save(update_fields=["count"])
        RequestLimit.objects.filter(expires_at__lt=datetime.fromtimestamp(now, tz=timezone.utc)).delete()
    return True
