from rest_framework import serializers
from .models import ShoppingItem, ShoppingHistory

class ShoppingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingItem
        fields = '__all__'

class ShoppingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingHistory
        fields = '__all__' 