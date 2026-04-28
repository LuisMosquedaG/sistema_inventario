from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_inicio, name='dashboard_inicio'),
]
