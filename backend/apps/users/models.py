# -*- coding: utf-8 -*-
# Django
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    phone = models.CharField(_('Telefono'), max_length=50)

    def __str__(self) -> str:
        return self.get_full_name()
