from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import ShoppingItem, ShoppingHistory
from .serializers import ShoppingItemSerializer
from django.db.models import Count
import re
from django.db.models import Q
from django.http import JsonResponse

import json
import inflect
p = inflect.engine()


# Hardcoded seasonal items and substitutes
SEASONAL_ITEMS = ['mangoes', 'watermelon', 'pumpkin', 'cranberries']
SUBSTITUTES = {
    'milk': ['almond milk', 'soy milk', 'oat milk'],
    'bread': ['whole wheat bread', 'gluten-free bread'],
    'butter': ['margarine', 'olive oil'],
}

CATEGORY_KEYWORDS = {
    'dairy': ['milk', 'cheese', 'butter', 'yogurt', 'paneer', 'curd', 'cream'],
    'fruits': ['apple', 'banana', 'mango', 'orange', 'grape', 'watermelon', 'pear', 'peach', 'plum', 'berry'],
    'vegetables': ['tomato', 'onion', 'potato', 'carrot', 'spinach', 'pumpkin', 'cabbage', 'lettuce', 'broccoli'],
    'bakery': ['bread', 'bun', 'cake', 'biscuit', 'cookie', 'roll', 'croissant'],
    'meat': ['chicken', 'beef', 'mutton', 'fish', 'egg', 'pork', 'lamb'],
    'beverages': ['juice', 'tea', 'coffee', 'soda', 'cola', 'water', 'drink'],
}

def infer_category(name, brand):
    name = name.lower()
    brand = (brand or '').lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name or kw in brand:
                return cat
    return 'other'

@api_view(['POST'])
def add_item(request):
    """Add or update an item in the shopping list, incrementing quantity if exists. Auto-categorizes if needed."""
    data = request.data
    name = data.get('name', '').strip().lower()
    name = p.singular_noun(name) or name

    quantity = int(data.get('quantity', 1))
    category = data.get('category', '').strip().lower() or 'other'
    brand = data.get('brand', '')
    price = data.get('price', None)
    user = request.user if request.user.is_authenticated else None

    # Auto-categorize if category is missing or 'other'
    if not category or category == 'other':
        category = infer_category(name, brand)

    item, created = ShoppingItem.objects.get_or_create(
        name=name, user=user,
        defaults={'quantity': str(quantity), 'category': category, 'brand': brand, 'price': price}
    )

    if not created:
        try:
            current_qty = int(item.quantity)
            item.quantity = str(current_qty + quantity)  # ✅ increment instead of overwrite
        except ValueError:
            item.quantity = str(quantity)  # fallback if quantity is not a valid number
        item.category = category
        item.brand = brand
        if price:
            item.price = price
        item.save()

    ShoppingHistory.objects.create(user=user, item=name, action='add')

    return Response({'success': True, 'item': ShoppingItemSerializer(item).data})


@api_view(['POST'])
def remove_item(request):
    """Remove or decrement an item from the shopping list. Supports fuzzy/plural matching."""
    data = request.data
    name = data.get('name', '').strip().lower()
    name = p.singular_noun(name) or name

    quantity = int(data.get('quantity', 1))  # default: remove 1
    user = request.user if request.user.is_authenticated else None

    # Try exact match first
    try:
        item = ShoppingItem.objects.get(name=name, user=user)
    except ShoppingItem.DoesNotExist:
        # Fuzzy/plural matching: try to find the closest match
        from difflib import get_close_matches
        # Get all item names for this user
        items_qs = ShoppingItem.objects.filter(user=user) if user else ShoppingItem.objects.all()
        item_names = [i.name for i in items_qs]
        # Try singular/plural forms
        candidates = set()
        candidates.add(name)
        candidates.add(p.plural(name))
        candidates.add(p.singular_noun(name) or name)
        # Add all user items that are close matches
        close = get_close_matches(name, item_names, n=1, cutoff=0.7)
        if close:
            match_name = close[0]
        else:
            # Try matching by substring if no close match
            match_name = next((n for n in item_names if name in n or n in name), None)
        if match_name:
            item = items_qs.get(name=match_name)
        else:
            return Response({'success': False, 'error': 'Item not found'}, status=404)

    try:
        current_qty = int(item.quantity)
    except ValueError:
        current_qty = 1  # fallback if not a number

    if current_qty > quantity:
        item.quantity = str(current_qty - quantity)
        item.save()
        action = 'update'
    else:
        item.delete()
        action = 'remove'

    # log history
    ShoppingHistory.objects.create(user=user, item=item.name, action=action)

    return Response({'success': True, 'action': action})


@api_view(['GET'])
def get_list(request):
    """Get the current shopping list."""
    user = request.user if request.user.is_authenticated else None
    items = ShoppingItem.objects.filter(user=user) if user else ShoppingItem.objects.all()
    serializer = ShoppingItemSerializer(items, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def get_suggestions(request):
    """Suggest items based on usage frequency, season, and current stock."""
    user = request.user if request.user.is_authenticated else None
    from collections import Counter

    # Step 1: Get user's add history
    raw_history = ShoppingHistory.objects.filter(user=user, action='add') \
        .values_list('item', flat=True)

    # Normalize names
    items = [p.singular_noun(i.lower().strip()) or i.lower().strip() for i in raw_history]

    # Step 2: Count frequent items
    freq_counts = Counter(items)
    freq_suggestions = [item for item, count in freq_counts.most_common(5)]

    # Step 3: Find shortages — frequently used items with 0 quantity
    shortages = []
    for item_name, count in freq_counts.items():
        if count >= 5:  # Used 5+ times
            try:
                item = ShoppingItem.objects.get(name=item_name, user=user)
                if int(item.quantity) == 0:
                    shortages.append(item_name)
            except ShoppingItem.DoesNotExist:
                shortages.append(item_name)  # Also suggest if completely removed
            except ValueError:
                continue  # Skip if quantity is invalid

    # Step 4: Seasonal & substitutes
    seasonal = SEASONAL_ITEMS
    last_item = ShoppingHistory.objects.filter(user=user, action='add').order_by('-timestamp').first()
    subs = []
    if last_item:
        key = p.singular_noun(last_item.item.lower().strip()) or last_item.item.lower().strip()
        if key in SUBSTITUTES:
            subs = SUBSTITUTES[key]

    return Response({
        'frequent': freq_suggestions,
        'seasonal': seasonal,
        'substitutes': subs,
        'shortages': shortages,
    })



@api_view(['GET'])
def search_items(request):
    query = request.GET.get('q', '').strip().lower()
    brand = request.GET.get('brand', '').strip().lower()
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    user = request.user if request.user.is_authenticated else None

    # Singularize input (e.g., "mangoes" → "mango")
    singular_query = p.singular_noun(query) or query

    # Optional: add synonym support
    synonym_map = {
        'aubergine': 'eggplant',
        'curd': 'yogurt',
        'mangoes': 'mango',
        'mangos': 'mango',
        'आम': 'mango',
        'सेब': 'apple',
        'दूध': 'milk',
        # Add more as needed
    }
    synonym_query = synonym_map.get(singular_query, singular_query)

    if not synonym_query:
        return Response({'error': 'No search query provided.'}, status=400)

    items = ShoppingItem.objects.filter(user=user) if user else ShoppingItem.objects.all()
    if synonym_query:
        items = items.filter(Q(name__icontains=synonym_query) | Q(category__icontains=synonym_query))
    if brand:
        items = items.filter(brand__icontains=brand)
    if min_price:
        items = items.filter(price__gte=min_price)
    if max_price:
        items = items.filter(price__lte=max_price)

    serializer = ShoppingItemSerializer(items, many=True)
    return Response(serializer.data)



from googletrans import Translator
@api_view(['POST'])
def translate(request):
    from googletrans import Translator
    data = request.data
    text = data.get('text', '')
    source = data.get('source', 'auto')
    
    translator = Translator()
    try:
        translated = translator.translate(text, src=source, dest='en')
        return Response({'translated': translated.text})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
def log_unmapped(request):
    phrase = request.data.get('text')
    lang = request.data.get('sourceLang')
    try:
        with open('unmapped_phrases.txt', 'a', encoding='utf-8') as f:
            f.write(f"[{lang}] {phrase}\n")
        return Response({'status': 'logged'})
    except Exception as e:
        return Response({'status': 'error', 'error': str(e)}, status=500)
def index(request):
    return render(request, 'shopping/index.html')




