from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from core.models import CustomUser
from django.conf import settings
from events.models import EventRegistration
from .forms import CustomUserRegistrationForm, UserQuestionnaireForm, ProfileForm, NotificationSettingsForm
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .models import Questionnaire, NotificationSettings
from .emails import send_templated_email


def is_admin(user):
    return user.is_superuser

@login_required
@user_passes_test(is_admin)
def admin_panel(request):
    """admin dashboard for managing users and event requests."""
    search_query = request.GET.get('search', '').strip()
    sort_option = request.GET.get('sort', '').strip()

    selected_options = {
        'username_asc': '',
        'username_desc': '',
        'age_asc': '',
        'age_desc': '',
        'newest': '',
        'oldest': '',
    }
    if sort_option in selected_options:
        selected_options[sort_option] = 'selected'

    users = CustomUser.objects.filter(is_superuser=False)

    pending_users = users.filter(is_approved=False, is_active=True).order_by('date_joined')
    approved_users = users.filter(is_approved=True, is_active=True)

    if search_query:
        approved_users = approved_users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(city__icontains=search_query)
        )

    if sort_option == 'username_asc':
        approved_users = approved_users.order_by('username')
    elif sort_option == 'username_desc':
        approved_users = approved_users.order_by('-username')
    elif sort_option == 'age_asc':
        approved_users = approved_users.order_by('age')
    elif sort_option == 'age_desc':
        approved_users = approved_users.order_by('-age')
    elif sort_option == 'newest':
        approved_users = approved_users.order_by('-date_joined')
    elif sort_option == 'oldest':
        approved_users = approved_users.order_by('date_joined')
    else:
        approved_users = approved_users.order_by('first_name', 'last_name')

    event_regs_pending  = EventRegistration.objects.filter(status='pending').count()
    event_regs_approved = EventRegistration.objects.filter(status='approved').count()
    event_regs_rejected = EventRegistration.objects.filter(status='rejected').count()

    return render(request, 'core/admin_panel.html', {
        'pending_users': pending_users,
        'approved_users': approved_users,
        'search_query': search_query,
        'sort_option': sort_option,
        'selected_options': selected_options,
        'event_regs_pending': event_regs_pending,
        'event_regs_approved': event_regs_approved,
        'event_regs_rejected': event_regs_rejected,
    })


@login_required
@user_passes_test(is_admin)
def approve_user(request, user_id):
    user = CustomUser.objects.get(id=user_id)

    if user.age >= 18 and (user.studies or user.works):
        user.is_approved = True
        user.save()
    return redirect('admin_panel')

@login_required
@user_passes_test(is_admin)
def reject_user(request, user_id):
    try:
        user = CustomUser.objects.get(id=user_id)
        user.delete() 
        messages.info(request, f"Потребителят {user.email} беше отхвърлен и изтрит.")
    except CustomUser.DoesNotExist:
        messages.error(request, "Потребителят не съществува.")
    return redirect('admin_panel')

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    user.delete()
    messages.success(request, "Потребителят беше успешно изтрит.")
    return redirect('admin_panel')


def register(request):
    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST)
        if form.is_valid():
            user = CustomUser.objects.create_user(
                username=form.cleaned_data['username'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
                age=form.cleaned_data['age'],
                city=form.cleaned_data['city'],
                studies=(form.cleaned_data['studies'] == 'yes'),
                education_place=form.cleaned_data['education_place'] if form.cleaned_data['studies'] == 'yes' else '',
                works=(form.cleaned_data['works'] == 'yes'),
                work_place=form.cleaned_data['work_place'] if form.cleaned_data['works'] == 'yes' else '',
                about=form.cleaned_data['about'],
                is_active=True,
                is_approved=False,
                password=form.cleaned_data['password']

            )
            messages.success(request, "Успешна регистрация! Очаквайте одобрение.")
            return redirect('login')
    else:
        form = CustomUserRegistrationForm()

    return render(request, 'register.html', {'form': form})

def home(request):
    return render(request, 'home.html')

def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user:
            if not user.is_superuser and not user.is_approved:
                messages.warning(request, 'Вашата регистрация все още не е одобрена от администратор.')
                return redirect('login')
            else:
                login(request, user)
                return redirect('home')
        else:
            messages.error(request, 'Невалидни данни. Опитайте отново.')

    return render(request, 'login.html')

def custom_logout(request):
    logout(request)
    return redirect('login')

@login_required
def fill_questionnaire(request):
    if Questionnaire.objects.filter(user=request.user).exists():
        return redirect('home') 

    if request.method == 'POST':
        form = UserQuestionnaireForm(request.POST)
        if form.is_valid():
            questionnaire = form.save(commit=False)
            questionnaire.user = request.user
            questionnaire.completed = True
            questionnaire.save()
            form.save_m2m()
            return redirect('thank_you')
    else:
        form = UserQuestionnaireForm()

    return render(request, 'fill_questionnaire.html', {'form': form})


@login_required
def edit_questionnaire(request):
    questionnaire = request.user.userquestionnaire
    if request.method == 'POST':
        form = UserQuestionnaireForm(request.POST, instance=questionnaire)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserQuestionnaireForm(instance=questionnaire)

    return render(request, 'edit_questionnaire.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def admin_event_registrations(request):
    pending_regs = EventRegistration.objects.filter(status='pending').order_by('-created_at')
    approved_regs = EventRegistration.objects.filter(status='approved').order_by('-created_at')
    rejected_regs = EventRegistration.objects.filter(status='rejected').order_by('-created_at')

    return render(request, 'core/admin_event_registrations.html', {
        'pending_regs': pending_regs,
        'approved_regs': approved_regs,
        'rejected_regs': rejected_regs,
    })


@login_required
@user_passes_test(is_admin)
def approve_registration(request, reg_id):
    reg = get_object_or_404(EventRegistration, id=reg_id)
    if reg.status != 'approved':
        reg.status = 'approved'
        reg.save() 
        messages.success(request, f'Заявката на {reg.full_name or reg.user.username} е одобрена.')
    else:
        messages.info(request, 'Заявката вече е одобрена.')
    return redirect('admin_event_registrations')


@login_required
@user_passes_test(is_admin)
def reject_registration(request, reg_id):
    reg = get_object_or_404(EventRegistration, id=reg_id)
    if reg.status != 'rejected':
        reg.status = 'rejected'
        reg.save()
        messages.success(request, f'Заявката на {reg.full_name or reg.user.username} е отхвърлена.')
    else:
        messages.info(request, 'Заявката вече е отхвърлена.')
    return redirect('admin_event_registrations')

@login_required
def my_profile(request):
    user = request.user
    questionnaire, _ = Questionnaire.objects.get_or_create(
        user=user,
        defaults={
            "full_name": (user.get_full_name() or user.username or "Потребител").strip(),
            "city": getattr(user, "city", "") or "",
            "can_travel_to_sofia": False,
            "about": "",
            "has_children": False,
            "wants_events_with_children": False,
            "why_join": "",
            "how_did_you_hear": "instagram",  
            "completed": False,
        },
    )

    prefs, _ = NotificationSettings.objects.get_or_create(user=user)

    if request.method == 'POST':
        which = request.POST.get('form', 'profile')

        if which == 'profile':
            form = ProfileForm(request.POST, request.FILES, instance=user)
            q_form = UserQuestionnaireForm(instance=questionnaire)
            notif_form = NotificationSettingsForm(instance=prefs)
            if form.is_valid():
                form.save()

                prefs = getattr(request.user, 'notificationsettings', None)
                should_email = (not prefs) or prefs.email_profile_changes
                if should_email and request.user.email:
                    ctx = {"recipient_name": request.user.first_name or request.user.username}
                    send_templated_email(
                        subject="LuxeLadies – Профилът е обновен",
                        to=[request.user.email],
                        txt_template="email/profile_updated.txt",
                        html_template="email/profile_updated.html",
                        context=ctx,
                    )

                messages.success(request, 'Профилът е обновен.')
                return redirect('my_profile')

        elif which == 'questionnaire':
            form = ProfileForm(instance=user)
            q_form = UserQuestionnaireForm(request.POST, instance=questionnaire)
            notif_form = NotificationSettingsForm(instance=prefs)
            if q_form.is_valid():
                q_form.save()

                should_email = (not prefs) or prefs.email_questionnaire_changes
                if should_email and user.email:
                    ctx = {"recipient_name": user.first_name or user.username}
                    send_templated_email(
                        subject="LuxeLadies – Отговорите във въпросника са обновени",
                        to=[user.email],
                        txt_template="email/questionnaire_updated.txt",
                        html_template="email/questionnaire_updated.html",
                        context=ctx,
                    )

                messages.success(request, 'Отговорите от въпросника са запазени.')
                return redirect('my_profile')

        elif which == 'notifications':
            form = ProfileForm(instance=user)
            q_form = UserQuestionnaireForm(instance=questionnaire)
            notif_form = NotificationSettingsForm(request.POST, instance=prefs)
            if notif_form.is_valid():
                prefs = notif_form.save()

                if user.email:
                    ctx = {
                        "recipient_name": user.first_name or user.username,
                        "prefs": prefs,
                    }
                    send_templated_email(
                        subject="LuxeLadies – Настройките за имейл известия са обновени",
                        to=[user.email],
                        txt_template="email/notifications_updated.txt",
                        html_template="email/notifications_updated.html",
                        context=ctx,
                    )

                messages.success(request, 'Настройките за известия са запазени.')
                return redirect('my_profile')

        else:
            form = ProfileForm(instance=user)
            q_form = UserQuestionnaireForm(instance=questionnaire)
            notif_form = NotificationSettingsForm(instance=prefs)

    else:
        form = ProfileForm(instance=user)
        q_form = UserQuestionnaireForm(instance=questionnaire)
        notif_form = NotificationSettingsForm(instance=prefs)

    approved_regs = (
        EventRegistration.objects
        .filter(user=user, status='approved', event__date_time__gte=timezone.now())
        .select_related('event').order_by('event__date_time')
    )
    approved_events = [r.event for r in approved_regs]

    past_regs = (
        EventRegistration.objects
        .filter(user=user, status='approved', event__date_time__lt=timezone.now())
        .select_related('event').order_by('-event__date_time')
    )
    past_events = [r.event for r in past_regs]

    return render(request, 'core/my_profile.html', {
        'form': form,
        'q_form': q_form,
        'notif_form': notif_form,
        'approved_events': approved_events,
        'past_events': past_events,
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) 
            messages.success(request, "Паролата е сменена успешно.")
            return redirect('my_profile')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'core/change_password.html', {'form': form})
