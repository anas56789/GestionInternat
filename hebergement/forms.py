from django import forms
from django.forms import inlineformset_factory

from .models import (
    Affectation,
    AnneeUniversitaire,
    Batiment,
    Chambre,
    DemandeHebergement,
    Justificatif,
)
from django.db.models import Max
# ============================================================
# DEMANDE D'HÉBERGEMENT
# ============================================================

class DemandeHebergementForm(forms.ModelForm):
    class Meta:
        model = DemandeHebergement

        fields = [
            "annee_universitaire",
            "motif",
            "distance_domicile",
            "situation_sociale",
            "commentaire",
        ]

        widgets = {
            "annee_universitaire": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "motif": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": (
                        "Expliquez pourquoi vous demandez "
                        "un hébergement."
                    ),
                }
            ),
            "distance_domicile": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": "0",
                    "step": "0.01",
                    "placeholder": (
                        "Distance en kilomètres"
                    ),
                }
            ),
            "situation_sociale": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": (
                        "Décrivez brièvement votre "
                        "situation sociale."
                    ),
                }
            ),
            "commentaire": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 3,
                    "placeholder": (
                        "Informations complémentaires "
                        "facultatives."
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        etudiant=None,
        **kwargs,
    ):
        """
        Le paramètre etudiant est envoyé par la vue.

        Il doit être retiré des paramètres avant l'appel
        au constructeur Django ModelForm.
        """
        self.etudiant = etudiant

        super().__init__(*args, **kwargs)

        self.fields[
            "annee_universitaire"
        ].queryset = (
            AnneeUniversitaire.objects
            .exclude(
                statut=(
                    AnneeUniversitaire
                    .Statut
                    .CLOTUREE
                )
            )
            .order_by("-date_debut")
        )

        self.fields[
            "annee_universitaire"
        ].empty_label = (
            "Sélectionnez une année universitaire"
        )

    def clean_distance_domicile(self):
        distance = self.cleaned_data.get(
            "distance_domicile"
        )

        if distance is not None and distance < 0:
            raise forms.ValidationError(
                (
                    "La distance du domicile ne peut "
                    "pas être négative."
                )
            )

        return distance

    def clean(self):
        donnees = super().clean()

        annee = donnees.get(
            "annee_universitaire"
        )

        if self.etudiant and annee:
            demandes_existantes = (
                DemandeHebergement.objects.filter(
                    etudiant=self.etudiant,
                    annee_universitaire=annee,
                )
            )

            if self.instance and self.instance.pk:
                demandes_existantes = (
                    demandes_existantes.exclude(
                        pk=self.instance.pk
                    )
                )

            if demandes_existantes.exists():
                raise forms.ValidationError(
                    (
                        "Vous avez déjà enregistré "
                        "une demande d'hébergement "
                        "pour cette année universitaire."
                    )
                )

        return donnees


# ============================================================
# JUSTIFICATIF
# ============================================================

class JustificatifForm(forms.ModelForm):
    class Meta:
        model = Justificatif

        fields = [
            "type_document",
            "fichier",
        ]

        widgets = {
            "type_document": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "fichier": forms.ClearableFileInput(
                attrs={
                    "class": "champ-fichier",
                    "accept": (
                        ".pdf,.jpg,.jpeg,.png"
                    ),
                }
            ),
        }


JustificatifFormSet = inlineformset_factory(
    DemandeHebergement,
    Justificatif,
    form=JustificatifForm,
    fields=[
        "type_document",
        "fichier",
    ],
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ============================================================
# AFFECTATION D'UNE CHAMBRE
# ============================================================

class AffectationForm(forms.ModelForm):
    class Meta:
        model = Affectation

        fields = [
            "chambre",
            "date_entree_prevue",
            "date_sortie_prevue",
            "statut",
        ]

        widgets = {
            "chambre": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "date_entree_prevue": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "date_sortie_prevue": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
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

        chambres_disponibles = [
            chambre.pk
            for chambre in (
                Chambre.objects
                .select_related("batiment")
                .filter(
                    est_active=True,
                    batiment__statut=(
                        Chambre._meta
                        .get_field("batiment")
                        .related_model
                        .Statut
                        .ACTIF
                    ),
                )
            )
            if (
                chambre.est_disponible_pour_affectation
                and chambre.nombre_places_disponibles > 0
            )
        ]

        self.fields["chambre"].queryset = (
            Chambre.objects
            .select_related("batiment")
            .filter(
                pk__in=chambres_disponibles
            )
            .order_by(
                "batiment__code",
                "etage",
                "numero",
            )
        )

        self.fields["statut"].choices = [
            (
                Affectation.Statut.PREVUE,
                "Prévue",
            ),
            (
                Affectation.Statut.ACTIVE,
                "Active",
            ),
        ]

    def clean(self):
        donnees = super().clean()

        date_entree = donnees.get(
            "date_entree_prevue"
        )

        date_sortie = donnees.get(
            "date_sortie_prevue"
        )

        statut = donnees.get("statut")

        if (
            date_entree
            and date_sortie
            and date_sortie < date_entree
        ):
            self.add_error(
                "date_sortie_prevue",
                (
                    "La date de sortie doit être "
                    "postérieure ou égale à la "
                    "date d'entrée."
                ),
            )

        if statut == Affectation.Statut.ACTIVE:
            self.add_error(
                "statut",
                (
                    "Créez d'abord l'affectation "
                    "avec le statut Prévue. "
                    "L'entrée réelle sera confirmée "
                    "ensuite."
                ),
            )

        return donnees


# ============================================================
# TRANSFERT D'UN ÉTUDIANT
# ============================================================

class TransfertEtudiantForm(forms.Form):
    nouvelle_chambre = forms.ModelChoiceField(
        queryset=Chambre.objects.none(),
        label="Nouvelle chambre",
        empty_label="Sélectionnez une chambre disponible",
        widget=forms.Select(
            attrs={
                "class": "champ",
            }
        ),
    )

    date_transfert = forms.DateField(
        label="Date du transfert",
        widget=forms.DateInput(
            attrs={
                "class": "champ",
                "type": "date",
            }
        ),
    )

    motif = forms.CharField(
        label="Motif du transfert",
        min_length=5,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "champ",
                "rows": 4,
                "maxlength": 500,
                "placeholder": (
                    "Exemple : problème technique, "
                    "changement de bâtiment ou "
                    "demande administrative."
                ),
            }
        ),
    )

    def __init__(
        self,
        *args,
        affectation=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.affectation = affectation

        chambres_possibles = (
            Chambre.objects
            .select_related(
                "batiment",
            )
            .filter(
                est_active=True,
                batiment__statut=Batiment.Statut.ACTIF,
            )
            .exclude(
                etat__in={
                    Chambre.Etat.COMPLETE,
                    Chambre.Etat.MAINTENANCE,
                    Chambre.Etat.HORS_SERVICE,
                }
            )
            .order_by(
                "batiment__code",
                "etage",
                "numero",
            )
        )

        if affectation:
            chambres_possibles = (
                chambres_possibles.exclude(
                    pk=affectation.chambre_id,
                )
            )

            date_minimale = (
                affectation.date_entree_reelle
                or affectation.date_entree_prevue
            )

            date_maximale = (
                affectation.date_sortie_prevue
            )

            self.fields[
                "date_transfert"
            ].widget.attrs.update(
                {
                    "min": date_minimale.strftime(
                        "%Y-%m-%d"
                    ),
                    "max": date_maximale.strftime(
                        "%Y-%m-%d"
                    ),
                }
            )

        chambres_disponibles_ids = [
            chambre.pk
            for chambre in chambres_possibles
            if chambre.nombre_places_disponibles > 0
        ]

        queryset_chambres_disponibles = (
            chambres_possibles.filter(
                pk__in=chambres_disponibles_ids,
            )
        )

        self.fields[
            "nouvelle_chambre"
        ].queryset = queryset_chambres_disponibles

        self.fields[
            "nouvelle_chambre"
        ].label_from_instance = (
            self.libelle_chambre
        )

    @staticmethod
    def libelle_chambre(chambre):
        places_disponibles = (
            chambre.nombre_places_disponibles
        )

        return (
            f"{chambre.batiment.code} / "
            f"Chambre {chambre.numero} — "
            f"Étage {chambre.etage} — "
            f"{places_disponibles} place(s) disponible(s)"
        )

    def clean_nouvelle_chambre(self):
        nouvelle_chambre = self.cleaned_data.get(
            "nouvelle_chambre"
        )

        if not nouvelle_chambre:
            return nouvelle_chambre

        if not self.affectation:
            raise forms.ValidationError(
                "L’affectation actuelle est introuvable."
            )

        if (
            nouvelle_chambre.pk
            == self.affectation.chambre_id
        ):
            raise forms.ValidationError(
                (
                    "La nouvelle chambre doit être "
                    "différente de la chambre actuelle."
                )
            )

        if not nouvelle_chambre.est_active:
            raise forms.ValidationError(
                "Cette chambre est désactivée."
            )

        if (
            nouvelle_chambre.batiment.statut
            != Batiment.Statut.ACTIF
        ):
            raise forms.ValidationError(
                (
                    "Le bâtiment de cette chambre "
                    "n’est pas actif."
                )
            )

        if nouvelle_chambre.etat in {
            Chambre.Etat.COMPLETE,
            Chambre.Etat.MAINTENANCE,
            Chambre.Etat.HORS_SERVICE,
        }:
            raise forms.ValidationError(
                (
                    "Cette chambre n’est pas disponible "
                    "pour un transfert."
                )
            )

        if (
            nouvelle_chambre.nombre_places_disponibles
            <= 0
        ):
            raise forms.ValidationError(
                (
                    "Cette chambre ne possède plus "
                    "de place disponible."
                )
            )

        return nouvelle_chambre

    def clean_date_transfert(self):
        date_transfert = self.cleaned_data.get(
            "date_transfert"
        )

        if not date_transfert:
            return date_transfert

        if not self.affectation:
            raise forms.ValidationError(
                "L’affectation actuelle est introuvable."
            )

        date_entree_reference = (
            self.affectation.date_entree_reelle
            or self.affectation.date_entree_prevue
        )

        if (
            date_entree_reference
            and date_transfert
            < date_entree_reference
        ):
            raise forms.ValidationError(
                (
                    "La date du transfert ne peut pas être "
                    "antérieure à la date d’entrée de "
                    "l’étudiant."
                )
            )

        if (
            self.affectation.date_sortie_prevue
            and date_transfert
            > self.affectation.date_sortie_prevue
        ):
            raise forms.ValidationError(
                (
                    "La date du transfert ne peut pas être "
                    "postérieure à la date de sortie prévue."
                )
            )

        annee = (
            self.affectation.annee_universitaire
        )

        if (
            date_transfert < annee.date_debut
            or date_transfert > annee.date_fin
        ):
            raise forms.ValidationError(
                (
                    "La date du transfert doit être comprise "
                    "dans l’année universitaire."
                )
            )

        return date_transfert

    def clean_motif(self):
        motif = (
            self.cleaned_data.get(
                "motif",
                "",
            )
            .strip()
        )

        if len(motif) < 5:
            raise forms.ValidationError(
                (
                    "Le motif doit contenir "
                    "au moins 5 caractères."
                )
            )

        return motif

    def clean(self):
        donnees = super().clean()

        if not self.affectation:
            raise forms.ValidationError(
                (
                    "L’affectation à transférer "
                    "n’a pas été fournie."
                )
            )

        if (
            self.affectation.statut
            != Affectation.Statut.ACTIVE
        ):
            raise forms.ValidationError(
                (
                    "Seule une affectation active "
                    "peut être transférée."
                )
            )

        return donnees
# ============================================================
# FORMULAIRE BÂTIMENT
# ============================================================

class BatimentForm(forms.ModelForm):
    class Meta:
        model = Batiment

        fields = [
            "code",
            "nom",
            "nombre_etages",
            "statut",
            "description",
        ]

        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : BAT-A",
                }
            ),
            "nom": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Nom du bâtiment",
                }
            ),
            "nombre_etages": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": 0,
                }
            ),
            "statut": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": "Description du bâtiment",
                }
            ),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "")

        code = code.strip().upper()

        if not code:
            raise forms.ValidationError(
                "Le code du bâtiment est obligatoire."
            )

        batiments_existants = Batiment.objects.filter(
            code__iexact=code,
        )

        if self.instance.pk:
            batiments_existants = batiments_existants.exclude(
                pk=self.instance.pk,
            )

        if batiments_existants.exists():
            raise forms.ValidationError(
                "Un bâtiment portant ce code existe déjà."
            )

        return code

    def clean_nom(self):
        nom = self.cleaned_data.get("nom", "")

        nom = nom.strip()

        if not nom:
            raise forms.ValidationError(
                "Le nom du bâtiment est obligatoire."
            )

        return nom

    def clean_nombre_etages(self):
        nombre_etages = self.cleaned_data.get(
            "nombre_etages"
        )

        if nombre_etages is None:
            raise forms.ValidationError(
                "Le nombre d’étages est obligatoire."
            )

        if nombre_etages < 0:
            raise forms.ValidationError(
                "Le nombre d’étages ne peut pas être négatif."
            )

        return nombre_etages

    def clean(self):
        donnees = super().clean()

        nombre_etages = donnees.get("nombre_etages")
        statut = donnees.get("statut")

        # Vérification pendant la modification d’un bâtiment.
        if self.instance.pk and nombre_etages is not None:
            etage_maximum = (
                self.instance.chambres.aggregate(
                    maximum=Max("etage")
                ).get("maximum")
            )

            if (
                etage_maximum is not None
                and nombre_etages < etage_maximum
            ):
                self.add_error(
                    "nombre_etages",
                    (
                        "Impossible de réduire le nombre "
                        f"d’étages à {nombre_etages}. "
                        "Une chambre existe actuellement "
                        f"à l’étage {etage_maximum}."
                    ),
                )

        # Empêcher la désactivation d’un bâtiment
        # contenant encore des étudiants.
        if (
            self.instance.pk
            and statut
            in {
                Batiment.Statut.INACTIF,
                Batiment.Statut.MAINTENANCE,
            }
        ):
            contient_affectations_actives = (
                Affectation.objects.filter(
                    chambre__batiment=self.instance,
                    statut=Affectation.Statut.ACTIVE,
                ).exists()
            )

            if contient_affectations_actives:
                self.add_error(
                    "statut",
                    (
                        "Ce bâtiment contient encore des "
                        "étudiants avec une affectation active. "
                        "Transférez ou clôturez leurs affectations "
                        "avant de changer son statut."
                    ),
                )

        return donnees


# ============================================================
# FORMULAIRE CHAMBRE
# ============================================================

class ChambreForm(forms.ModelForm):
    class Meta:
        model = Chambre

        fields = [
            "batiment",
            "numero",
            "etage",
            "capacite",
            "type_chambre",
            "etat",
            "est_active",
            "description",
        ]

        widgets = {
            "batiment": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "numero": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : 101",
                }
            ),
            "etage": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": 0,
                }
            ),
            "capacite": forms.NumberInput(
                attrs={
                    "class": "champ",
                    "min": 1,
                }
            ),
            "type_chambre": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "etat": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
            "est_active": forms.CheckboxInput(
                attrs={
                    "class": "case-cocher",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "champ",
                    "rows": 4,
                    "placeholder": "Description ou équipements",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        batiments_disponibles = (
            Batiment.objects
            .exclude(
                statut=Batiment.Statut.INACTIF,
            )
            .order_by("code")
        )

        # Pendant une modification, conserver le bâtiment
        # actuel dans la liste même s’il est devenu inactif.
        if (
            self.instance.pk
            and self.instance.batiment_id
        ):
            batiments_disponibles = (
                Batiment.objects.filter(
                    pk=self.instance.batiment_id,
                )
                | batiments_disponibles
            )

            batiments_disponibles = (
                batiments_disponibles
                .distinct()
                .order_by("code")
            )

        self.fields["batiment"].queryset = (
            batiments_disponibles
        )

    def clean_numero(self):
        numero = self.cleaned_data.get("numero", "")

        numero = numero.strip().upper()

        if not numero:
            raise forms.ValidationError(
                "Le numéro de la chambre est obligatoire."
            )

        return numero

    def clean_etage(self):
        etage = self.cleaned_data.get("etage")

        if etage is None:
            raise forms.ValidationError(
                "L’étage est obligatoire."
            )

        if etage < 0:
            raise forms.ValidationError(
                "L’étage ne peut pas être négatif."
            )

        return etage

    def clean_capacite(self):
        capacite = self.cleaned_data.get("capacite")

        if capacite is None:
            raise forms.ValidationError(
                "La capacité est obligatoire."
            )

        if capacite < 1:
            raise forms.ValidationError(
                "La capacité doit être au moins égale à 1."
            )

        return capacite

    def clean(self):
        donnees = super().clean()

        batiment = donnees.get("batiment")
        numero = donnees.get("numero")
        etage = donnees.get("etage")
        capacite = donnees.get("capacite")
        etat = donnees.get("etat")
        est_active = donnees.get("est_active")

        # ====================================================
        # ÉTAGE COMPATIBLE AVEC LE BÂTIMENT
        # ====================================================

        if (
            batiment
            and etage is not None
            and etage > batiment.nombre_etages
        ):
            self.add_error(
                "etage",
                (
                    "L’étage de la chambre ne peut pas "
                    "dépasser le nombre d’étages du bâtiment "
                    f"({batiment.nombre_etages})."
                ),
            )

        # ====================================================
        # NUMÉRO UNIQUE DANS LE MÊME BÂTIMENT
        # ====================================================

        if batiment and numero:
            chambres_existantes = Chambre.objects.filter(
                batiment=batiment,
                numero__iexact=numero,
            )

            if self.instance.pk:
                chambres_existantes = (
                    chambres_existantes.exclude(
                        pk=self.instance.pk,
                    )
                )

            if chambres_existantes.exists():
                self.add_error(
                    "numero",
                    (
                        "Une chambre portant ce numéro existe "
                        "déjà dans le bâtiment sélectionné."
                    ),
                )

        # ====================================================
        # NOMBRE ACTUEL D’OCCUPANTS
        # ====================================================

        nombre_occupants = 0

        if self.instance.pk:
            nombre_occupants = (
                Affectation.objects.filter(
                    chambre=self.instance,
                    statut=Affectation.Statut.ACTIVE,
                ).count()
            )

        # ====================================================
        # CAPACITÉ SUPÉRIEURE OU ÉGALE AUX OCCUPANTS
        # ====================================================

        if (
            capacite is not None
            and capacite < nombre_occupants
        ):
            self.add_error(
                "capacite",
                (
                    "La capacité ne peut pas être inférieure "
                    f"au nombre actuel d’occupants "
                    f"({nombre_occupants})."
                ),
            )

        # ====================================================
        # ÉTAT COMPLET
        # ====================================================

        if (
            etat == Chambre.Etat.COMPLETE
            and capacite is not None
            and nombre_occupants < capacite
        ):
            self.add_error(
                "etat",
                (
                    "La chambre ne peut pas être déclarée "
                    "complète tant que toutes ses places "
                    "ne sont pas occupées."
                ),
            )

        # ====================================================
        # MAINTENANCE OU HORS SERVICE
        # ====================================================

        if (
            etat
            in {
                Chambre.Etat.MAINTENANCE,
                Chambre.Etat.HORS_SERVICE,
            }
            and nombre_occupants > 0
        ):
            self.add_error(
                "etat",
                (
                    "Cette chambre contient encore "
                    f"{nombre_occupants} étudiant(s). "
                    "Transférez ou clôturez leurs affectations "
                    "avant de la rendre indisponible."
                ),
            )

        # ====================================================
        # DÉSACTIVATION
        # ====================================================

        if (
            est_active is False
            and nombre_occupants > 0
        ):
            self.add_error(
                "est_active",
                (
                    "Une chambre occupée ne peut pas être "
                    "désactivée. Transférez ou clôturez d’abord "
                    "les affectations actives."
                ),
            )

        # Une chambre inactive ne doit pas rester disponible.
        if (
            est_active is False
            and etat
            in {
                Chambre.Etat.DISPONIBLE,
                Chambre.Etat.PARTIELLE,
                Chambre.Etat.COMPLETE,
            }
        ):
            self.add_error(
                "etat",
                (
                    "Une chambre inactive doit être placée "
                    "en maintenance ou hors service."
                ),
            )

        return donnees


# ============================================================
# ANNÉE UNIVERSITAIRE
# ============================================================

class AnneeUniversitaireForm(forms.ModelForm):
    class Meta:
        model = AnneeUniversitaire

        fields = [
            "libelle",
            "date_debut",
            "date_fin",
            "statut",
        ]

        widgets = {
            "libelle": forms.TextInput(
                attrs={
                    "class": "champ",
                    "placeholder": "Exemple : 2026-2027",
                }
            ),
            "date_debut": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "date_fin": forms.DateInput(
                attrs={
                    "class": "champ",
                    "type": "date",
                }
            ),
            "statut": forms.Select(
                attrs={
                    "class": "champ",
                }
            ),
        }

    def clean_libelle(self):
        libelle = self.cleaned_data.get(
            "libelle",
            "",
        ).strip()

        if not libelle:
            raise forms.ValidationError(
                "Le libellé de l’année universitaire est obligatoire."
            )

        annees_existantes = (
            AnneeUniversitaire.objects
            .filter(
                libelle__iexact=libelle,
            )
        )

        if self.instance.pk:
            annees_existantes = (
                annees_existantes.exclude(
                    pk=self.instance.pk,
                )
            )

        if annees_existantes.exists():
            raise forms.ValidationError(
                "Une année universitaire portant ce libellé existe déjà."
            )

        return libelle

    def clean(self):
        donnees = super().clean()

        date_debut = donnees.get(
            "date_debut"
        )

        date_fin = donnees.get(
            "date_fin"
        )

        statut = donnees.get(
            "statut"
        )

        # ====================================================
        # COHÉRENCE DES DATES
        # ====================================================

        if (
            date_debut
            and date_fin
            and date_fin <= date_debut
        ):
            self.add_error(
                "date_fin",
                (
                    "La date de fin doit être "
                    "postérieure à la date de début."
                ),
            )

        # ====================================================
        # CHEVAUCHEMENT AVEC UNE AUTRE ANNÉE
        # ====================================================

        if date_debut and date_fin:
            annees_chevauchantes = (
                AnneeUniversitaire.objects
                .filter(
                    date_debut__lte=date_fin,
                    date_fin__gte=date_debut,
                )
            )

            if self.instance.pk:
                annees_chevauchantes = (
                    annees_chevauchantes.exclude(
                        pk=self.instance.pk,
                    )
                )

            if annees_chevauchantes.exists():
                autre_annee = (
                    annees_chevauchantes
                    .order_by("date_debut")
                    .first()
                )

                self.add_error(
                    "date_debut",
                    (
                        "Cette période chevauche l’année "
                        f"universitaire {autre_annee.libelle}."
                    ),
                )

                self.add_error(
                    "date_fin",
                    (
                        "Choisissez une période qui ne chevauche "
                        "aucune autre année universitaire."
                    ),
                )

        # ====================================================
        # UNE SEULE ANNÉE ACTIVE
        # ====================================================

        if (
            statut
            == AnneeUniversitaire.Statut.ACTIVE
        ):
            autre_annee_active = (
                AnneeUniversitaire.objects
                .filter(
                    statut=(
                        AnneeUniversitaire
                        .Statut
                        .ACTIVE
                    ),
                )
            )

            if self.instance.pk:
                autre_annee_active = (
                    autre_annee_active.exclude(
                        pk=self.instance.pk,
                    )
                )

            if autre_annee_active.exists():
                annee_active = (
                    autre_annee_active.first()
                )

                self.add_error(
                    "statut",
                    (
                        "L’année universitaire "
                        f"{annee_active.libelle} est déjà active. "
                        "Clôturez-la avant d’en activer une autre."
                    ),
                )

        # ====================================================
        # PROTECTION D’UNE ANNÉE CLÔTURÉE
        # ====================================================

        if (
            self.instance.pk
            and self.instance.statut
            == AnneeUniversitaire.Statut.CLOTUREE
        ):
            champs_modifies = []

            if (
                date_debut
                and date_debut
                != self.instance.date_debut
            ):
                champs_modifies.append(
                    "date_debut"
                )

            if (
                date_fin
                and date_fin
                != self.instance.date_fin
            ):
                champs_modifies.append(
                    "date_fin"
                )

            if (
                statut
                and statut
                != self.instance.statut
            ):
                champs_modifies.append(
                    "statut"
                )

            if champs_modifies:
                self.add_error(
                    None,
                    (
                        "Une année universitaire clôturée "
                        "ne peut plus être modifiée."
                    ),
                )

        # ====================================================
        # PROTECTION DES AFFECTATIONS EXISTANTES
        # ====================================================

        if (
            self.instance.pk
            and date_debut
            and date_fin
        ):
            affectations = (
                Affectation.objects
                .filter(
                    annee_universitaire=self.instance,
                )
            )

            affectation_trop_tot = (
                affectations
                .filter(
                    date_entree_prevue__lt=date_debut,
                )
                .exists()
            )

            affectation_trop_tard = (
                affectations
                .filter(
                    date_sortie_prevue__gt=date_fin,
                )
                .exists()
            )

            if affectation_trop_tot:
                self.add_error(
                    "date_debut",
                    (
                        "Cette date est postérieure à la date "
                        "d’entrée prévue d’une affectation existante."
                    ),
                )

            if affectation_trop_tard:
                self.add_error(
                    "date_fin",
                    (
                        "Cette date est antérieure à la date "
                        "de sortie prévue d’une affectation existante."
                    ),
                )

        return donnees