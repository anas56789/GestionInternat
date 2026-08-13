# GestionInternat

Application web de gestion d'un internat universitaire développée avec Django.

## Présentation

GestionInternat centralise la gestion des étudiants, demandes d'hébergement, justificatifs, affectations, chambres, bâtiments, finances, paiements, réclamations, notifications et audit.

## Acteurs

- Administrateur
- Responsable de l'internat
- Étudiant

## Fonctionnalités principales

### Responsable / Administration
- Tableau de bord avec statistiques
- Gestion des étudiants
- Traitement des demandes
- Validation des justificatifs
- Affectations et transferts de chambres
- Gestion des bâtiments, chambres et années universitaires
- Gestion des frais et paiements
- Gestion des réclamations
- Notifications
- Audit des actions

### Étudiant
- Authentification
- Tableau de bord personnel
- Dépôt et suivi des demandes
- Consultation de l'hébergement
- Situation financière et paiements
- Réclamations
- Notifications
- Profil étudiant
- Déconnexion avec confirmation

## Technologies

- Python
- Django
- SQLite en développement
- HTML5 / CSS3 / JavaScript
- Pillow
- Git / GitHub

## Structure

```text
GestionInternat/
├── accounts/
├── audit/
├── config/
├── dashboard/
├── etudiants/
├── finances/
├── hebergement/
├── notifications/
├── reclamations/
├── manage.py
├── requirements.txt
└── .env.example
```

## Installation

```powershell
git clone <URL_DU_DEPOT>
cd GestionInternat
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Application locale :

```text
http://127.0.0.1:8000/
```

## Configuration

Exemple `.env` :

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SECURE_HSTS_SECONDS=3600
```

## Sécurité

Le projet utilise notamment :
- authentification Django ;
- utilisateur personnalisé ;
- contrôle d'accès par rôle ;
- CSRF ;
- validation des mots de passe ;
- cookies de session sécurisés ;
- journalisation des actions sensibles ;
- contrôles métier sur demandes, affectations, chambres et paiements.

## Fichiers non versionnés

- `.venv/`
- `db.sqlite3`
- autres bases SQLite locales
- `media/`
- `logs/`
- `.env`
- scripts locaux de génération de données DEMO

## Captures d'écran

Les captures principales seront intégrées au rapport PFA :
- connexion ;
- dashboard Responsable ;
- demandes ;
- affectations ;
- chambres et bâtiments ;
- finances ;
- réclamations ;
- notifications ;
- dashboard Étudiant ;
- hébergement ;
- profil.

## Contexte académique

Projet de Fin d'Année (PFA)

**Sujet :** Conception et développement d'une application de gestion de l'internat d'un établissement universitaire.

## Auteur

Anass Mardi  
Étudiant en Ingénierie Informatique & Réseaux

## État

Version fonctionnelle de démonstration, en phase de validation, documentation et préparation de soutenance.
