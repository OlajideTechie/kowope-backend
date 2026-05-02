# common/models.py

import uuid
from django.db import models

class Area(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100, unique=True)
    lga = models.CharField(max_length=100, default="")
    state = models.CharField(max_length=50, default="Lagos")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name