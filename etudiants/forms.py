from django import forms
from django.core.exceptions import ValidationError

from accounts.models import Utilisateur

from .models import Etudiant
from django.contrib.auth import get_user_model

from .models import Etudiant

class EtudiantForm(forms.ModelForm):
    class Meta:
        model = Etudiant

        fields = [
            "utilisateur",
            "matricule",
            "cne",
            "date_naissance",
            "sexe",
            "adresse",
            "ville_origine",
            "filiere",
            "niveau_etude",
            "telephone_contact_urgence",
            "nom_contact_urgence",
            "lien_contact_urgence",
            "photo",
            "statut",
        ]

        widgets = {
            "utilisateur": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "matricule": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : EMSI2026001",
                }
            ),
            "cne": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Code national étudiant",
                }
            ),
            "date_naissance": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "sexe": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "adresse": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 3,
                    "placeholder": "Adresse complète",
                }
            ),
            "ville_origine": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Ville d'origine",
                }
            ),
            "filiere": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : Ingénierie informatique",
                }
            ),
            "niveau_etude": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : 3IIR",
                }
            ),
            "telephone_contact_urgence": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Numéro du contact d'urgence",
                }
            ),
            "nom_contact_urgence": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Nom du contact d'urgence",
                }
            ),
            "lien_contact_urgence": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : Père, mère, frère",
                }
            ),
            "photo": forms.ClearableFileInput(
                attrs={
                    "class": "champ-fichier",
                    "accept": "image/*",
                }
            ),
            "statut": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        utilisateurs_disponibles = (
            Utilisateur.objects
            .filter(
                role=Utilisateur.Role.ETUDIANT,
                is_active=True,
            )
            .order_by(
                "last_name",
                "first_name",
                "username",
            )
        )

        if self.instance and self.instance.pk:
            utilisateurs_disponibles = (
                utilisateurs_disponibles.filter(
                    profil_etudiant__isnull=True,
                )
                | Utilisateur.objects.filter(
                    pk=self.instance.utilisateur_id
                )
            )

        else:
            utilisateurs_disponibles = (
                utilisateurs_disponibles.filter(
                    profil_etudiant__isnull=True
                )
            )

        self.fields["utilisateur"].queryset = (
            utilisateurs_disponibles.distinct()
        )

        self.fields["utilisateur"].label_from_instance = (
            self.afficher_utilisateur
        )

    @staticmethod
    def afficher_utilisateur(utilisateur):
        nom_complet = utilisateur.get_full_name().strip()

        if nom_complet:
            return (
                f"{nom_complet} "
                f"({utilisateur.username})"
            )

        return utilisateur.username

    def clean_matricule(self):
        matricule = (
            self.cleaned_data["matricule"]
            .strip()
            .upper()
        )

        profils = Etudiant.objects.filter(
            matricule__iexact=matricule
        )

        if self.instance.pk:
            profils = profils.exclude(
                pk=self.instance.pk
            )

        if profils.exists():
            raise ValidationError(
                "Ce matricule est déjà utilisé."
            )

        return matricule

    def clean_cne(self):
        cne = (
            self.cleaned_data["cne"]
            .strip()
            .upper()
        )

        profils = Etudiant.objects.filter(
            cne__iexact=cne
        )

        if self.instance.pk:
            profils = profils.exclude(
                pk=self.instance.pk
            )

        if profils.exists():
            raise ValidationError(
                "Ce CNE est déjà utilisé."
            )

        return cne

    def clean_telephone_contact_urgence(self):
        telephone = (
            self.cleaned_data[
                "telephone_contact_urgence"
            ]
            .strip()
        )

        caracteres_autorises = {
            "+",
            " ",
            "-",
            "(",
            ")",
        }

        for caractere in telephone:
            if (
                not caractere.isdigit()
                and caractere not in caracteres_autorises
            ):
                raise ValidationError(
                    (
                        "Le numéro de téléphone contient "
                        "des caractères invalides."
                    )
                )

        return telephone


Utilisateur = get_user_model()


class ProfilEtudiantPersonnelForm(forms.ModelForm):
    prenom = forms.CharField(
        label="Prénom",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "champ",
                "placeholder": "Votre prénom",
                "autocomplete": "given-name",
            }
        ),
    )

    nom = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "champ",
                "placeholder": "Votre nom",
                "autocomplete": "family-name",
            }
        ),
    )

    email = forms.EmailField(
        label="Adresse e-mail",
        widget=forms.EmailInput(
            attrs={
                "class": "champ",
                "placeholder": "nom@exemple.com",
                "autocomplete": "email",
            }
        ),
    )

    class Meta:
        model = Etudiant

        # Ces champs peuvent être modifiés par l'étudiant.
        # Les données administratives restent en lecture seule :
        # matricule, CNE, filière, niveau et statut.
        fields = [
            "date_naissance",
            "sexe",
            "adresse",
            "ville_origine",
        ]

        widgets = {
            "date_naissance": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "sexe": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "adresse": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": "Votre adresse actuelle",
                }
            ),
            "ville_origine": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Votre ville d’origine",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            utilisateur = self.instance.utilisateur

            self.fields["prenom"].initial = (
                utilisateur.first_name
            )
            self.fields["nom"].initial = (
                utilisateur.last_name
            )
            self.fields["email"].initial = (
                utilisateur.email
            )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        utilisateur_id = None

        if self.instance and self.instance.pk:
            utilisateur_id = self.instance.utilisateur_id

        email_deja_utilise = (
            Utilisateur.objects
            .filter(email__iexact=email)
            .exclude(pk=utilisateur_id)
            .exists()
        )

        if email_deja_utilise:
            raise forms.ValidationError(
                "Cette adresse e-mail est déjà utilisée."
            )

        return email

    def save(self, commit=True):
        profil = super().save(commit=False)
        utilisateur = profil.utilisateur

        utilisateur.first_name = (
            self.cleaned_data["prenom"].strip()
        )
        utilisateur.last_name = (
            self.cleaned_data["nom"].strip()
        )
        utilisateur.email = self.cleaned_data["email"]

        if commit:
            utilisateur.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "email",
                ]
            )

            profil.save()
            self.save_m2m()

        return profil
