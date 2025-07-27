from django.contrib import admin
from .models import ShoppingItem, ShoppingHistory

admin.site.register(ShoppingItem)
admin.site.register(ShoppingHistory)
