from django import forms

from .models import Reclamation


class ReclamationForm(forms.ModelForm):
    class Meta:
        model = Reclamation

        fields = [
            "chambre",
            "titre",
            "description",
            "categorie",
            "priorite",
            "piece_jointe",
        ]

        widgets = {
            "chambre": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "titre": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Titre de la réclamation",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 6,
                    "placeholder": (
                        "Décrivez précisément le problème rencontré."
                    ),
                }
            ),
            "categorie": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "priorite": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "piece_jointe": forms.ClearableFileInput(
                attrs={
                    "class": "champ",
                    "accept": ".pdf,.jpg,.jpeg,.png",
                }
            ),
        }

    def __init__(self, *args, etudiant=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.etudiant = etudiant

        if etudiant:
            affectation_active = (
                etudiant.affectations
                .filter(statut="ACTIVE")
                .select_related("chambre")
                .first()
            )

            if affectation_active:
                self.fields["chambre"].queryset = (
                    self.fields["chambre"].queryset.filter(
                        pk=affectation_active.chambre_id
                    )
                )

                self.fields["chambre"].initial = (
                    affectation_active.chambre
                )
            else:
                self.fields["chambre"].queryset = (
                    self.fields["chambre"].queryset.none()
                )

                self.fields["chambre"].required = False
