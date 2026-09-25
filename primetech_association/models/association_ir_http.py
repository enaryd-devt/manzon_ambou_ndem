# -*- coding: utf-8 -*-
"""Session behaviour for the association member area."""

from odoo import models


class AssociationIrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Open the dedicated dashboard as soon as an ordinary member logs in.

        This is deliberately computed for the current web session.  Storing an
        ``ir.actions.client`` on ``res.users.action_id`` is not supported by
        Odoo and caused saving errors on user accounts.
        """
        info = super().session_info()
        if self.env.user.has_group(
            "primetech_association.group_association_member"
        ):
            dashboard_action = self.env.ref(
                "primetech_association.action_association_dashboard_client",
                raise_if_not_found=False,
            )
            if dashboard_action:
                info["home_action_id"] = dashboard_action.id
        return info
