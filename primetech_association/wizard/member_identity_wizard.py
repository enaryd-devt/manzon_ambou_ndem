# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


# Profils autorisés à corriger le nom d'un membre et à lui associer un compte
# utilisateur (le vice-secrétaire hérite du secrétaire).
IDENTITY_GROUP_XMLIDS = (
    "primetech_association.group_association_meeting_secretary",
    "primetech_association.group_association_manager",
    "primetech_association.group_association_admin",
)


class AssociationMemberIdentityWizard(models.TransientModel):
    """Modification limitée de la fiche membre : nom et compte utilisateur.

    Le secrétaire n'a pas le droit d'écrire sur la fiche membre ; cet
    assistant lui permet de modifier uniquement ces informations.
    """

    _name = "association.member.identity.wizard"
    _description = "Modifier le nom et le compte utilisateur d'un membre"

    member_id = fields.Many2one("association.member", string="Membre", required=True, readonly=True)
    first_name = fields.Char(string="Prénom")
    last_name = fields.Char(string="Nom")
    full_name = fields.Char(string="Nom complet", compute="_compute_full_name")
    user_id = fields.Many2one(
        "res.users", string="Compte utilisateur",
        domain="[('share', '=', False)]",
        help="Compte qui donne accès à l'espace membre de cette personne.",
    )

    @api.model
    def _check_identity_access(self):
        if not any(self.env.user.has_group(xmlid) for xmlid in IDENTITY_GROUP_XMLIDS):
            raise AccessError(_(
                "Seuls le secrétaire, le responsable et l'administrateur peuvent "
                "modifier le nom d'un membre ou lui associer un compte utilisateur."
            ))

    @api.model
    def default_get(self, fields_list):
        self._check_identity_access()
        values = super().default_get(fields_list)
        member = self.env["association.member"].browse(values.get("member_id")).exists()
        if member:
            first_name, last_name = member.first_name, member.last_name
            if not first_name and not last_name and member.name:
                parts = member.name.split()
                first_name, last_name = parts[0], " ".join(parts[1:])
            values.update({
                "first_name": first_name,
                "last_name": last_name,
                "user_id": member.user_id.id,
            })
        return values

    @api.depends("first_name", "last_name")
    def _compute_full_name(self):
        for wizard in self:
            wizard.full_name = " ".join(
                part.strip() for part in (wizard.first_name, wizard.last_name) if part and part.strip()
            )

    def action_apply(self):
        self.ensure_one()
        self._check_identity_access()
        if not self.full_name:
            raise ValidationError(_("Le prénom ou le nom du membre est obligatoire."))
        member = self.member_id.sudo()
        if self.user_id:
            other = member.search([
                ("user_id", "=", self.user_id.id),
                ("id", "!=", member.id),
            ], limit=1)
            if other:
                raise ValidationError(_(
                    "Le compte %(user)s est déjà associé au membre %(member)s."
                ) % {"user": self.user_id.display_name, "member": other.display_name})
        # sudo() garde l'utilisateur courant : l'historique de la fiche
        # indique bien qui a fait la modification.
        member.write({
            "first_name": (self.first_name or "").strip() or False,
            "last_name": (self.last_name or "").strip() or False,
            "user_id": self.user_id.id or False,
        })
        return {"type": "ir.actions.act_window_close"}
