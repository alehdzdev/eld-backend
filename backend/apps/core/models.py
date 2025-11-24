# -*- coding: utf-8 -*-
from datetime import datetime

# Django
from django.db import models


class BaseModel(models.Model):
    """Base model.

    Add base fields that could be helpful with API response in all models.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(default=None, null=True, blank=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = datetime.now()
        self.save()

    class Meta:
        abstract = True
