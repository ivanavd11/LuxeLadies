from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from core.models import Questionnaire
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseNotAllowed
from .models import Event, EventRegistration
from .forms import EventFilterForm, EventRegistrationForm

@login_required
def events_home(request):
    return render(request, 'events/events_home.html')

@login_required
def all_events(request):
    events = (
        Event.objects
        .filter(date_time__gte=timezone.now())  
        .order_by('date_time')
    )
    form = EventFilterForm(request.GET or None)

    if form.is_valid():
        date = form.cleaned_data.get('date')
        city = form.cleaned_data.get('city')
        interests = form.cleaned_data.get('interests')
        kid_friendly = form.cleaned_data.get('kid_friendly')

        if date:
            events = events.filter(date_time__date=date)

        if city:
            events = events.filter(city=city)

        if interests:
            events = events.filter(interests=interests)

        if kid_friendly == 'yes':
            events = events.filter(is_kid_friendly=True)
        elif kid_friendly == 'no':
            events = events.filter(is_kid_friendly=False)

    return render(request, 'events/all_events.html', {'events': events, 'form': form})

@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    is_past = event.date_time <= timezone.now()

    if request.method == "POST" and request.POST.get("action") == "register":
        if is_past:
            messages.warning(request, "Събитието вече е минало.")
            return redirect("event_detail", event_id=event.id)

        full_name = (
            request.POST.get("full_name")
            or request.user.get_full_name()
            or request.user.username
        )

        EventRegistration.objects.get_or_create(
            user=request.user,
            event=event,
            defaults={"status": "pending", "full_name": full_name},
        )
        return redirect("event_detail", event_id=event.id)

    existing_registration = None
    if request.user.is_authenticated:
        existing_registration = EventRegistration.objects.filter(
            event=event, user=request.user
        ).first()

    return render(request, "events/event_detail.html", {
        "event": event,
        "existing_registration": existing_registration,
        "is_past": is_past,
    })

@login_required
def recommended_events(request):
    user = request.user

    try:
        questionnaire = Questionnaire.objects.get(user=user)
    except Questionnaire.DoesNotExist:
        return render(request, 'events/events_home.html')

    user_city = questionnaire.city.strip()
    can_travel = questionnaire.can_travel_to_sofia
    has_children = questionnaire.has_children
    wants_with_children = questionnaire.wants_events_with_children

    allowed_cities = [user_city]
    if can_travel:
        allowed_cities.append("София") 

    events = Event.objects.filter(
        city__in=allowed_cities,
        date_time__gte=timezone.now()
    )

    if has_children:
        if not wants_with_children:
            events = events.filter(is_kid_friendly=False)
    else:
        events = events.filter(is_kid_friendly=False)

    events = events.distinct().order_by('date_time')

    return render(request, 'events/recommended_events.html', {'events': events})


def past_events_list(request):
    events = (
        Event.objects
        .filter(date_time__lt=timezone.now())
        .order_by('-date_time')
    )
    return render(request, 'events/past_events.html', {'events': events})

@login_required
def register_for_event(request, event_id):
    event = get_object_or_404(Event, pk=event_id)

    if event.date_time <= timezone.now():
        messages.warning(request, "Събитието вече е минало.")
        return redirect("event_detail", event_id=event.id)

    if request.method == "POST":
        form = EventRegistrationForm(request.POST)
        if form.is_valid():
            reg = form.save(commit=False)
            reg.user = request.user
            reg.event = event

            if event.is_kid_friendly and (not reg.child_name or reg.child_age is None):
                form.add_error(None, "Това събитие е за деца – моля, попълни името и възрастта на детето.")
                return render(request, "events/register_event.html", {"form": form, "event": event})

            if not event.is_kid_friendly:
                reg.child_name = None
                reg.child_age = None

            try:
                reg.save()  
            except Exception:
                form.add_error(None, "Вече имаш подадена заявка за това събитие.")
                return render(request, "events/register_event.html", {"form": form, "event": event})

            return redirect("register_thanks", event_id=event.id)
    else:
        initial = {}
        if request.user.get_full_name():
            initial["full_name"] = request.user.get_full_name()
        else:
            initial["full_name"] = request.user.username
        form = EventRegistrationForm(initial=initial)

    return render(request, "events/register_event.html", {"form": form, "event": event})

@login_required
def register_thanks(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'events/register_thanks.html', {'event': event})

