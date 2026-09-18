# -*- coding: utf-8 -*-

{
    "name": "PrimeTech Association Management",

    "summary": "Gestion complète des membres, réunions, cotisations et finances d'association",

    "description": """
PrimeTech Association Management
================================

PrimeTech Association Management est une application Odoo conçue pour piloter
les activités administratives, financières et statutaires d'une association
depuis un espace unique. Le module couvre le cycle complet de gestion :
adhérents, bureaux exécutifs, cotisations, encaissements, réunions, présences,
sanctions disciplinaires, procès-verbaux, comptes membres et trésorerie.

Fonctionnalités principales
---------------------------

* Gestion des membres : fiches adhérents, catégories, fonctions, compétences,
  statuts, photos, contacts et cartes de membre.
* Organisation associative : bureaux exécutifs, composition des comités et
  fonctions officielles.
* Cotisations : création des cotisations, génération des membres concernés,
  cycles de cotisation, pénalités de retard, suivi des montants dus, payés et
  restants.
* Encaissements : paiements directs, paiements depuis le compte membre,
  affectations automatiques, gestion des surplus et historique complet.
* Réunions : convocation, ordre du jour, liste d'appel, quorum, cotisations en
  séance, résolutions, incidents, sanctions et procès-verbal.
* Discipline : suivi des incidents, décisions disciplinaires, sanctions
  financières, suspensions, actions correctives et levées de sanction.
* Finances : comptes de trésorerie, mouvements financiers, dons, recettes,
  dépenses, comptes membres et rapports.
* Sécurité par rôle : administrateur, responsable, utilisateur, président,
  secrétaire, trésorier et censeur de réunion.
* Reporting : liste des membres, cartes, relevés, rapports disciplinaires,
  rapports de cotisation de réunion et procès-verbaux.

Comment utiliser le module
--------------------------

1. Configurer l'association depuis Associations > Configuration :
   nom de l'association, numérotation des membres, règles de cotisation,
   gestion des surplus, comptes de règlement et paramètres de rapports.
2. Définir les utilisateurs et leurs groupes d'accès :
   Administrateur Association, Responsable Association, Utilisateur Association,
   Président de réunion, Secrétaire de réunion, Trésorier de réunion ou Censeur
   de réunion.
3. Créer les membres depuis Associations > Adhérents > Membres, puis compléter
   les informations personnelles, la fonction, la catégorie, la photo et les
   coordonnées.
4. Mettre en place le bureau exécutif depuis Vie associative > Bureau exécutif
   afin d'identifier les responsables officiels de l'association.
5. Créer les cotisations depuis Finances > Cotisations et encaissements >
   Cotisations, générer les membres concernés, confirmer puis démarrer le cycle.
6. Enregistrer les paiements depuis Encaissements ou directement depuis une
   cotisation, une réunion ou un compte membre.
7. Organiser une réunion depuis Vie associative > Réunions : préparer la
   convocation, générer la liste d'appel, saisir les présences, gérer les
   cotisations de séance, enregistrer les résolutions et préparer le
   procès-verbal.
8. Suivre les incidents et sanctions depuis l'onglet de réunion ou depuis Vie
   associative > Discipline et sanctions.
9. Consulter les rapports depuis les boutons d'impression et l'assistant de
   rapports/relevés.

Bonnes pratiques
----------------

* Affecter uniquement les groupes nécessaires à chaque utilisateur afin que les
  menus, vues et boutons correspondent exactement à son niveau d'accès.
* Créer les comptes de trésorerie avant de commencer les encaissements.
* Vérifier la liste d'appel et clôturer les décisions disciplinaires avant de
  préparer le procès-verbal.
* Mettre à jour régulièrement les cycles de cotisation pour garder les soldes
  des membres cohérents.
""",

    "version": "18.0.1.0.0",

    "author": "PrimeTech Services",

    "website": "https://www.primetechafrik.com",

    "category": "Services",

    "license": "LGPL-3",

    "depends": [
        "base",
        "mail",
        "contacts",
        "web",
    ],

    "data": [

        # =====================================================
        # SECURITY
        # =====================================================

        "security/association_security.xml",
        "security/ir.model.access.csv",

        # =====================================================
        # DATA
        # =====================================================

        "data/association_sequence.xml",
        "data/member_function_data.xml",
        "data/bank_sequence.xml",
        "data/association_cron.xml",

        # =====================================================
        # VIEWS
        # =====================================================

        "views/dashboard_views.xml",

        "views/member_views.xml",
        "views/member_card_wizard_views.xml",
        "views/member_card_views.xml",

        "views/committee_views.xml",

        "views/subscription_views.xml",
        "views/subscription_penalty_recap_views.xml",
        "views/payment_views.xml",
        "views/subscription_period_views.xml",
        "views/donation_views.xml",
        "views/income_views.xml",
        "views/expense_views.xml",
        "views/fund_views.xml",

       

        "views/meeting_views.xml",
        "views/meeting_subscription_session_views.xml",
        "views/attendance_views.xml",
        "views/penalty_views.xml",
        "views/res_config_settings_views.xml",

        # =====================================================
        # REPORT
        # =====================================================

        "report/member_card_template.xml",
        "report/member_card_report.xml",
        "report/member_directory_report.xml",
        "report/statement_report.xml",

        "report/meeting_minutes_report.xml",
        "report/meeting_minutes_template.xml",
        "report/meeting_subscription_session_report.xml",

        # Banque / Trésorerie
        "views/fund_transaction_views.xml",

        "views/member_function_views.xml",

        "views/subscription_payment_wizard_views.xml",

        "views/member_account_views.xml",
        "views/member_account_transaction_views.xml",
        "views/association_payment_surplus_wizard_views.xml",
        "views/meeting_collection_surplus_wizard_views.xml",
        "views/member_wallet_transaction_views.xml",
        "views/subscription_cycle_close_wizard_views.xml",
        "views/meeting_subscription_cycle_start_wizard_views.xml",
        "views/member_account_subscription_payment_wizard_views.xml",

        # =====================================================
        # MENUS
        # =====================================================

        "views/menu_views.xml",
        "views/statement_report_wizard_views.xml",

        # The configuration menu is a child of menu_association_root, which
        # is defined above.  Load it after the root menu to support a clean
        # first installation as well as module upgrades.
        "views/configuration_views.xml",

    ],


    "assets": {
        "web.assets_backend": [
            "primetech_association/static/src/dashboard/association_dashboard.js",
            "primetech_association/static/src/dashboard/association_dashboard.xml",
            "primetech_association/static/src/dashboard/association_dashboard.scss",
            "primetech_association/static/src/scss/member_card.scss",
            "primetech_association/static/src/scss/member_list_filter.scss",

            "primetech_association/static/src/js/refresh_subscription_table.js",
            "primetech_association/static/src/js/member_list_filter.js",
        ],
    },

    "demo": [],

    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],

    "installable": True,

    "application": True,

    "auto_install": False,
}
