from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin class for CustomUser, inherits the standard Django UserAdmin.
    """
    # defines which fields the search engine works on in the list view; 
    # that is, which fields we can search on
    search_fields = ['username', 'email', 'first_name', 'last_name']

    # which columns to display in the users table
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_active']