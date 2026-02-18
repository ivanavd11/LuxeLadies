from django.contrib import admin, messages
from .models import Event, EventRegistration

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "date_time", "price")
    search_fields = ("title", "city", "description")
    list_filter = ("city",)
    date_hierarchy = "date_time"
    ordering = ("-date_time",)

@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['event', 'full_name', 'status', 'created_at']
    list_filter = ['status', 'event']
    search_fields = ['full_name', 'child_name', 'user__email']
    raw_id_fields = ['user', 'event']
    actions = ['approve_registration', 'reject_registration']

    @admin.action(description="Одобри избраните заявки")
    def approve_registration(self, request, queryset):
        changed = 0
        for registration in queryset:
            if registration.status != 'approved':
                registration.status = 'approved'
                registration.save()  
                changed += 1
        self.message_user(request, f"Одобрени {changed} заявки.", level=messages.SUCCESS)

    @admin.action(description="Откажи избраните заявки")
    def reject_registration(self, request, queryset):
        changed = 0
        for registration in queryset:
            if registration.status != 'rejected':
                registration.status = 'rejected'
                registration.save()  
                changed += 1
        self.message_user(request, f"Отказани {changed} заявки.", level=messages.WARNING)