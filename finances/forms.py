from decimal import Decimal

from django import forms
from django.utils import timezone

from hebergement.models import AnneeUniversitaire

from .models import FraisHebergement, Paiement

from django.db.models import Sum
class FraisHebergementForm(forms.ModelForm):
    class Meta:
        model = FraisHebergement

        fields = [
            "etudiant",
            "annee_universitaire",
            "montant_total",
            "date_echeance",
            "commentaire",
            "est_actif",
        ]

        widgets = {
            "etudiant": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "annee_universitaire": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "montant_total": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Exemple : 5000.00",
                }
            ),
            "date_echeance": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "commentaire": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": "Commentaire facultatif",
                }
            ),
            "est_actif": forms.CheckboxInput(
                attrs={
                    "class": "case-cocher",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["annee_universitaire"].queryset = (
            AnneeUniversitaire.objects.exclude(
                statut=AnneeUniversitaire.Statut.CLOTUREE
            ).order_by("-date_debut")
        )

        if not self.instance.pk:
            self.fields["est_actif"].initial = True
        if self.instance and self.instance.pk:
            self.fields["etudiant"].disabled = True
            self.fields["annee_universitaire"].disabled = True

            self.fields["etudiant"].help_text = (
            "L'étudiant ne peut pas être modifié après "
            "la création des frais."
        )

        self.fields["annee_universitaire"].help_text = (
        "L'année universitaire ne peut pas être "
        "modifiée après la création des frais."
        )

        self.fields["montant_total"].widget.attrs["min"] = str(
        self.instance.montant_paye
        )

        self.fields["montant_total"].help_text = (
        "Le montant total ne peut pas être inférieur "
        f"au montant déjà validé de "
        f"{self.instance.montant_paye} DH."
        )
    def clean_montant_total(self):
        montant = self.cleaned_data.get("montant_total")

        if montant is None:
            return montant

        if montant <= Decimal("0.00"):
            raise forms.ValidationError(
            "Le montant total doit être strictement positif."
        )

        if self.instance and self.instance.pk:
            montant_deja_valide = self.instance.montant_paye

        if montant < montant_deja_valide:
            raise forms.ValidationError(
                (
                    "Le montant total ne peut pas être inférieur "
                    "au montant déjà validé de "
                    f"{montant_deja_valide} DH."
                )
            )

        return montant

    def clean_date_echeance(self):
        date_echeance = self.cleaned_data.get("date_echeance")

        if (
            not self.instance.pk
            and date_echeance
            and date_echeance < timezone.localdate()
        ):
            raise forms.ValidationError(
                "La date d'échéance ne peut pas être passée."
            )

        return date_echeance


class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement

        fields = [
            "montant",
            "date_paiement",
            "mode_paiement",
            "reference",
            "commentaire",
        ]

        widgets = {
            "montant": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Montant payé",
                }
            ),
            "date_paiement": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "mode_paiement": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "reference": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": (
                        "Référence facultative pour les espèces"
                    ),
                }
            ),
            "commentaire": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": "Commentaire facultatif",
                }
            ),
        }

    def __init__(
        self,
        *args,
        frais_hebergement=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.frais_hebergement = frais_hebergement

        if frais_hebergement:
            montant_restant = frais_hebergement.montant_restant

            self.fields["montant"].widget.attrs["max"] = str(
                montant_restant
            )

            self.fields["montant"].help_text = (
                f"Montant restant : {montant_restant} DH"
            )

        self.fields["date_paiement"].initial = timezone.localdate()

    def clean_montant(self):
        montant = self.cleaned_data.get("montant")

        if montant is None:
            return montant

        if montant <= Decimal("0.00"):
            raise forms.ValidationError(
                "Le montant doit être strictement positif."
            )

        if (
            self.frais_hebergement
            and montant > self.frais_hebergement.montant_restant
        ):
            raise forms.ValidationError(
                (
                    "Le paiement ne peut pas dépasser le montant "
                    f"restant de "
                    f"{self.frais_hebergement.montant_restant} DH."
                )
            )

        return montant

    def clean_reference(self):
        reference = self.cleaned_data.get("reference")

        if reference:
            return reference.strip()

        return None


class AnnulationPaiementForm(forms.Form):
    motif_annulation = forms.CharField(
        label="Motif d'annulation",
        min_length=5,
        widget=forms.Textarea(
            attrs={
                "class": "champ",
                "rows": 4,
                "placeholder": (
                    "Expliquez la raison de l'annulation."
                ),
            }
        ),
    )

    def clean_motif_annulation(self):
        motif = self.cleaned_data["motif_annulation"].strip()

        if len(motif) < 5:
            raise forms.ValidationError(
                "Le motif doit contenir au moins 5 caractères."
            )

        return motif


class DeclarationPaiementEtudiantForm(forms.ModelForm):
    preuve_paiement = forms.FileField(
        label="Preuve de paiement",
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "champ champ-fichier",
                "accept": (
                    ".pdf,.jpg,.jpeg,.png,"
                    "application/pdf,image/jpeg,image/png"
                ),
            }
        ),
        help_text=(
            "Formats acceptés : PDF, JPG, JPEG ou PNG. "
            "Taille maximale : 5 Mo."
        ),
    )

    class Meta:
        model = Paiement

        fields = [
            "montant",
            "date_paiement",
            "mode_paiement",
            "reference",
            "preuve_paiement",
            "commentaire",
        ]

        widgets = {
            "montant": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": "0.01",
                    "step": "0.01",
                    "placeholder": "Montant versé",
                }
            ),
            "date_paiement": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "mode_paiement": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "reference": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": (
                        "Référence du virement, de la carte "
                        "ou du chèque"
                    ),
                }
            ),
            "commentaire": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": (
                        "Commentaire facultatif pour "
                        "l'administration"
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        frais_hebergement=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.frais_hebergement = frais_hebergement
        self.montant_en_attente = Decimal("0.00")
        self.montant_declarable = Decimal("0.00")

        self.fields["date_paiement"].initial = (
            timezone.localdate()
        )

        self.fields["reference"].required = True

        # L'étudiant ne peut pas déclarer un paiement
        # en espèces depuis son espace.
        self.fields["mode_paiement"].choices = [
            (valeur, libelle)
            for valeur, libelle
            in Paiement.ModePaiement.choices
            if valeur
            != Paiement.ModePaiement.ESPECES
        ]

        if frais_hebergement:
            self.montant_en_attente = (
                frais_hebergement
                .paiements
                .filter(
                    statut=Paiement.Statut.EN_ATTENTE,
                )
                .exclude(pk=self.instance.pk)
                .aggregate(
                    total=Sum("montant")
                )["total"]
                or Decimal("0.00")
            )

            self.montant_declarable = max(
                frais_hebergement.montant_restant
                - self.montant_en_attente,
                Decimal("0.00"),
            )

            self.fields["montant"].widget.attrs["max"] = str(
                self.montant_declarable
            )

            self.fields["montant"].help_text = (
                "Montant encore déclarable : "
                f"{self.montant_declarable} DH. "
                "Les déclarations en attente sont déjà réservées."
            )

    def clean_montant(self):
        montant = self.cleaned_data.get("montant")

        if montant is None:
            return montant

        if montant <= Decimal("0.00"):
            raise forms.ValidationError(
                "Le montant doit être strictement positif."
            )

        if (
            self.frais_hebergement
            and montant > self.montant_declarable
        ):
            raise forms.ValidationError(
                (
                    "Le montant déclaré ne peut pas dépasser "
                    f"{self.montant_declarable} DH."
                )
            )

        return montant

    def clean_date_paiement(self):
        date_paiement = self.cleaned_data.get(
            "date_paiement"
        )

        if (
            date_paiement
            and date_paiement > timezone.localdate()
        ):
            raise forms.ValidationError(
                "La date du paiement ne peut pas être future."
            )

        return date_paiement

    def clean_reference(self):
        reference = (
            self.cleaned_data
            .get("reference", "")
            .strip()
        )

        if not reference:
            raise forms.ValidationError(
                "La référence du paiement est obligatoire."
            )

        return reference
