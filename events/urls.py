from django.urls import path
from . import views

urlpatterns = [
    path('', views.events_home, name='events_home'),
    path('past/', views.past_events_list, name='events_past'),  
    path('all/', views.all_events, name='all_events'),
    path('recommended/', views.recommended_events, name='recommended_events'),
    path('<int:event_id>/', views.event_detail, name='event_detail'),
    path('register/<int:event_id>/', views.register_for_event, name='register_for_event'),
    path('register/<int:event_id>/thanks/', views.register_thanks, name='register_thanks'),
]