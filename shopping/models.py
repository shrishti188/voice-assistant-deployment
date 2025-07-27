from django.db import models
from django.contrib.auth.models import User

CATEGORY_CHOICES = [
    ('dairy', 'Dairy'),
    ('fruits', 'Fruits'),
    ('vegetables', 'Vegetables'),
    ('bakery', 'Bakery'),
    ('meat', 'Meat'),
    ('beverages', 'Beverages'),
    ('other', 'Other'),
]

class ShoppingItem(models.Model):
    name = models.CharField(max_length=100)
    quantity = models.CharField(max_length=50, default='1')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    brand = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.quantity})"

class ShoppingHistory(models.Model):
    ACTION_CHOICES = [
        ('add', 'Add'),
        ('remove', 'Remove'),
        ('update', 'Update'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    item = models.CharField(max_length=100)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} {self.action} {self.item} at {self.timestamp}"
