"""
URL configuration for luxeladies project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core import views as core_views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', core_views.custom_login, name='login'),
    path('accounts/logout/', core_views.custom_logout, name='logout'),
    path('', core_views.home, name='home'),
    path('register/', core_views.register, name='register'),
    
    path('admin-panel/', core_views.admin_panel, name='admin_panel'),
    path('admin-panel/approve/<int:user_id>/', core_views.approve_user, name='approve_user'),
    path('admin-panel/reject/<int:user_id>/', core_views.reject_user, name='reject_user'),
    path('admin-panel/delete/<int:user_id>/', core_views.delete_user, name='delete_user'),
    path('questionnaire/', core_views.fill_questionnaire, name='questionnaire'),
    path('thank-you/', TemplateView.as_view(template_name='thank_you.html'), name='thank_you'),
    path('events/', include('events.urls')),
    
    path('admin-panel/event-registrations/', core_views.admin_event_registrations, name='admin_event_registrations'),
    path('admin-panel/event-registrations/<int:reg_id>/approve/', core_views.approve_registration, name='approve_registration'),
    path('admin-panel/event-registrations/<int:reg_id>/reject/', core_views.reject_registration, name='reject_registration'),
    path('profile/', core_views.my_profile, name='my_profile'),
    path('profile/change-password/', core_views.change_password, name='change_password'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

