from django import forms
from .models import Questionnaire, Interest, NotificationSettings
from django.contrib.auth import get_user_model

class CustomUserRegistrationForm(forms.Form):
    """
    User self-registration form (without directly creating the model).
    Collects basic data and validates: - 18 years of age
                                       - passwords match
    """
    username = forms.CharField(label='Потребителско име', max_length=30)
    first_name = forms.CharField(label='Име', max_length=30)
    last_name = forms.CharField(label='Фамилия', max_length=30)
    email = forms.EmailField(label='Имейл')
    age = forms.IntegerField(label='Възраст', min_value=1)
    city = forms.CharField(label='Град', max_length=50)

    password = forms.CharField(label='Парола', widget=forms.PasswordInput)
    confirm_password = forms.CharField(label='Повтори паролата', widget=forms.PasswordInput)

    studies = forms.ChoiceField(
        label='Учите ли?', choices=[('yes', 'Да'), ('no', 'Не')], widget=forms.RadioSelect
    )
    education_place = forms.CharField(label='Учебно заведение', max_length=100, required=False)

    works = forms.ChoiceField(
        label='Работите ли?', choices=[('yes', 'Да'), ('no', 'Не')], widget=forms.RadioSelect
    )
    work_place = forms.CharField(label='Месторабота', max_length=100, required=False)

    about = forms.CharField(
        label='Информация за вас', widget=forms.Textarea, required=False
    )

    def clean(self):
        """ 
        Centralized form validation.
        """
        cleaned_data = super().clean()
        age = cleaned_data.get("age")
        if age is not None and age < 18:
            self.add_error('age', "Трябва да имате навършени 18 години, за да се регистрирате.")
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password != confirm_password:
            self.add_error('confirm_password', "Паролите не съвпадат.")


class UserQuestionnaireForm(forms.ModelForm):
    """
    ModelForm for the user questionnaire.
    """
    has_friend = forms.TypedChoiceField(
        label="Имаш ли приятелка, която е член на LuxeLadies?",
        choices=[('yes', 'Да'), ('no', 'Не')],
        widget=forms.RadioSelect,
        coerce=lambda v: v == 'yes', 
        empty_value=None,
        required=True,
    )
    friend_name = forms.CharField(
        label="Как се казва тя?",
        required=False,
    )

    class Meta:
        model = Questionnaire
        exclude = ['user', 'completed']
        labels = {
            'full_name': 'Трите Ви имена *',
            'city': 'Местоживеене (град/село) *',
            'can_travel_to_sofia': 'Повечето ни събития са в София. Имате ли възможност да пътувате? *',
            'interests': 'Кои теми те интересуват? Можеш да избереш няколко. *',
            'about': 'Разкажи ни за себе си. С какво се занимаваш и какви са твоите интереси? *',
            'has_children': 'Имате ли деца? *',
            'wants_events_with_children': 'Интересувате ли се от събития с деца?',
            'why_join': 'Защо искаш да се присъединиш към LuxeLadies? *',
            'instagram': 'Инстаграм акаунт (по желание)',
            'tiktok': 'TikTok акаунт (по желание)',
            'linkedin': 'LinkedIn акаунт (по желание)',
            'how_did_you_hear': 'Как разбра за нас? *',
        }
        widgets = {
            'interests': forms.CheckboxSelectMultiple(),
            'can_travel_to_sofia': forms.RadioSelect(choices=[(True, 'Да'), (False, 'Не')]),
            'has_children': forms.RadioSelect(choices=[(True, 'Да'), (False, 'Не')]),
            'wants_events_with_children': forms.RadioSelect(choices=[(True, 'Да'), (False, 'Не')]),
            'how_did_you_hear': forms.Select(choices=[
                ('instagram', 'Instagram'),
                ('tiktok', 'TikTok'),
                ('facebook', 'Facebook'),
                ('youtube', 'YouTube'),
                ('friend', 'От приятелка'),
                ('google', 'Търсене в Гугъл'),
            ])
        }

    def __init__(self, *args, **kwargs):
        """
        Sets initial values
        """
        super().__init__(*args, **kwargs)

        inst = self.instance if getattr(self.instance, 'pk', None) else None

        has_f_initial = None
        if self.data:
            has_f_initial = (self.data.get('has_friend') == 'yes')
        elif inst is not None:
            hf_val = getattr(inst, 'has_friend', "")
            if hf_val is None:
                hf_val = bool(getattr(inst, 'friend_name', "").strip())
            has_f_initial = bool(hf_val)

        if has_f_initial is not None:
            self.fields['has_friend'].initial = 'yes' if has_f_initial else 'no'
            self.fields['friend_name'].required = has_f_initial

    def clean(self):
        """Make friend_name mandatory when has_friend is True,
        and nullifies it when has_friend is False.
        """
        cleaned = super().clean()
        has_f = cleaned.get('has_friend') 
        fn = (cleaned.get('friend_name') or '').strip()

        if has_f:
            if not fn:
                self.add_error('friend_name', "Моля, въведи име на приятелката.")
            cleaned['friend_name'] = fn
        else:
            cleaned['friend_name'] = ''
        return cleaned


User = get_user_model()


class ProfileForm(forms.ModelForm):
    """
    Profile edit form.
    """
    remove_avatar = forms.BooleanField(
        label="Премахни снимката",
        required=False
    )
    class Meta:
        model = User
        fields = ["avatar", "first_name", "last_name", "username", "email"]
        widgets = {
            "avatar": forms.FileInput(attrs={
                "class": "sr-file",   
                "accept": "image/*",
            }),
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "last_name":  forms.TextInput(attrs={"class": "input"}),
            "username":   forms.TextInput(attrs={"class": "input"}),
            "email":      forms.EmailInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        """
        Makes names optional.
        """
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = False
        self.fields["last_name"].required = False
        self.fields["email"].required = True
        self.fields["username"].required = True
        self.fields['avatar'].required = False

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError("Това потребителско име е заето.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("Този имейл вече е зает.")
        return email
    
    def save(self, commit=True):
        """
        When checked, remove_avatar deletes the physical file and resets the field to zero.
        """
        user = super().save(commit=False)

        if self.cleaned_data.get("remove_avatar"):
            if user.avatar:
                try:
                    user.avatar.delete(save=False)
                except Exception:
                    pass
            user.avatar = None

        if commit:
            user.save()
        return user


class NotificationSettingsForm(forms.ModelForm):
    """
    Form to change email notification preferences.
    """
    class Meta:
        model = NotificationSettings
        fields = [
            'email_event_reminders',
            'email_event_status_changes',
            'email_recommendations',
            'email_profile_changes',
            'email_questionnaire_changes',
            'email_news',
        ]
        labels = {
            'email_event_reminders': 'Известия за събития, за които съм записана',
            'email_event_status_changes': 'Известия за одобрена/отхвърлена заявка за събитие',
            'email_recommendations': 'Известия за събития, подходящи за мен',
            'email_profile_changes': 'Известия при промяна на лични данни',
            'email_questionnaire_changes': 'Известия при промяна на отговори от въпросника',
            'email_news': 'Нови предложения и новини от LuxeLadies',
        }
        widgets = {f: forms.CheckboxInput(attrs={'class': 'checkbox'}) for f in fields}