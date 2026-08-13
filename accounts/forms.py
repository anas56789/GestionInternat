from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from .models import Utilisateur

class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(
            attrs={
                "class": "champ",
                "placeholder": "Nom d'utilisateur",
                "autocomplete": "username",
            }
        ),
    )

    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(
            attrs={
                "class": "champ",
                "placeholder": "Mot de passe",
                "autocomplete": "current-password",
            }
        ),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)

        if not user.is_active:
            raise forms.ValidationError(
                "Ce compte a été désactivé.",
                code="compte_inactif",
            )

class InscriptionEtudiantForm(UserCreationForm):
    first_name = forms.CharField(
        label="Prénom",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "Votre prénom",
                "autocomplete": "given-name",
            }
        ),
    )

    last_name = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "Votre nom",
                "autocomplete": "family-name",
            }
        ),
    )

    username = forms.CharField(
        label="Nom d'utilisateur",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "Choisissez un nom d'utilisateur",
                "autocomplete": "username",
            }
        ),
    )

    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "exemple@email.com",
                "autocomplete": "email",
            }
        ),
    )

    password1 = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "Créez un mot de passe sécurisé",
                "autocomplete": "new-password",
            }
        ),
    )

    password2 = forms.CharField(
        label="Confirmation du mot de passe",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "champ-inscription",
                "placeholder": "Confirmez votre mot de passe",
                "autocomplete": "new-password",
            }
        ),
    )

    accepter_conditions = forms.BooleanField(
        label=(
            "J'accepte les conditions d'utilisation "
            "et la politique de confidentialité."
        ),
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "case-inscription",
            }
        ),
    )

    class Meta:
        model = Utilisateur

        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "password1",
            "password2",
        ]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if Utilisateur.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "Ce nom d'utilisateur est déjà utilisé."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if Utilisateur.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "Cette adresse e-mail possède déjà un compte."
            )

        return email

    def save(self, commit=True):
        utilisateur = super().save(commit=False)

        utilisateur.first_name = (
            self.cleaned_data["first_name"].strip()
        )

        utilisateur.last_name = (
            self.cleaned_data["last_name"].strip()
        )

        utilisateur.email = (
            self.cleaned_data["email"].strip().lower()
        )

        # Sécurité :
        # impossible de créer un admin/responsable
        # depuis l'inscription publique.
        utilisateur.role = Utilisateur.Role.ETUDIANT
        utilisateur.is_staff = False
        utilisateur.is_superuser = False
        utilisateur.is_active = True

        if commit:
            utilisateur.save()

        return utilisateur

class UtilisateurCreationForm(UserCreationForm):
    class Meta:
        model = Utilisateur

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "password1",
            "password2",
        ]

        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Nom d'utilisateur",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Prénom",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Nom",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Adresse e-mail",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["password1"].widget.attrs.update(
            {
                "class": "champ",
                "placeholder": "Mot de passe",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "class": "champ",
                "placeholder": "Confirmation du mot de passe",
            }
        )

        self.fields["email"].required = True

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if Utilisateur.objects.filter(
            username__iexact=username
        ).exists():
            raise forms.ValidationError(
                "Ce nom d'utilisateur est déjà utilisé."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if Utilisateur.objects.filter(
            email__iexact=email
        ).exists():
            raise forms.ValidationError(
                "Cette adresse e-mail est déjà utilisée."
            )

        return email


class UtilisateurModificationForm(forms.ModelForm):
    class Meta:
        model = Utilisateur

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
        ]

        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "champ",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "champ",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "champ",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "champ",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "case-cocher",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].required = True

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        utilisateurs = Utilisateur.objects.filter(
            username__iexact=username
        )

        if self.instance.pk:
            utilisateurs = utilisateurs.exclude(
                pk=self.instance.pk
            )

        if utilisateurs.exists():
            raise forms.ValidationError(
                "Ce nom d'utilisateur est déjà utilisé."
            )

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        utilisateurs = Utilisateur.objects.filter(
            email__iexact=email
        )

        if self.instance.pk:
            utilisateurs = utilisateurs.exclude(
                pk=self.instance.pk
            )

        if utilisateurs.exists():
            raise forms.ValidationError(
                "Cette adresse e-mail est déjà utilisée."
            )

        return email
