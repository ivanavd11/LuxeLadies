from django.shortcuts import redirect
from django.urls import reverse

class QuestionnaireRequiredMiddleware:
    """
    Middleware that ensures that each logged-in user has completed the questionnaire 
    before accessing the rest of the site.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if not user.is_authenticated:
            return self.get_response(request)

        if user.is_superuser:
            return self.get_response(request)

        # We miss some specific paths
        allowed_paths = [
            reverse('logout'),
            reverse('questionnaire'),
        ]
        if request.path in allowed_paths or request.path.startswith('/admin/'):
            return self.get_response(request)

        if not hasattr(user, 'questionnaire'):
            return redirect('questionnaire')

        return self.get_response(request)