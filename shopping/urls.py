from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('add_item/', views.add_item, name='add_item'),
    path('remove_item/', views.remove_item, name='remove_item'),
    path('get_list/', views.get_list, name='get_list'),
    path('get_suggestions/', views.get_suggestions, name='get_suggestions'),
    path('search_items/', views.search_items, name='search_items'),
    path('translate/', views.translate),
    path('log_unmapped/', views.log_unmapped),
 

] 