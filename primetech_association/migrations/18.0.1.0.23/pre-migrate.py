# -*- coding: utf-8 -*-
"""Priorité de règlement : passage d'un nombre à 5 niveaux en texte.

L'ancienne valeur numérique (10 par défaut, 1 réglé en premier) est
convertie vers les nouveaux niveaux :

* 1            -> "1" Très haute
* 2 à 9        -> "2" Haute (saisi comme plus prioritaire que la valeur par défaut)
* 10           -> "3" Normale (ancienne valeur par défaut)
* plus de 10   -> "4" Basse
"""

TABLES = (
    "association_subscription",
    "association_membership_fee",
    "association_member_situation_adjustment",
    "association_member_activation_wizard",
)


def migrate(cr, version):
    for table in TABLES:
        cr.execute(
            """
            SELECT data_type FROM information_schema.columns
             WHERE table_name = %s AND column_name = 'payment_priority'
            """,
            (table,),
        )
        row = cr.fetchone()
        if not row or row[0] != "integer":
            continue
        cr.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN payment_priority TYPE varchar
            USING CASE
                WHEN payment_priority IS NULL THEN '3'
                WHEN payment_priority <= 1 THEN '1'
                WHEN payment_priority < 10 THEN '2'
                WHEN payment_priority = 10 THEN '3'
                ELSE '4'
            END
            """
        )
