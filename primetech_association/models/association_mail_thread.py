# -*- coding: utf-8 -*-
from odoo import models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def message_post(self, *args, **kwargs):
        """Keep automatic association chatter logs internal by default.

        The association workflows use ``message_post`` as an audit trail after
        button actions.  In databases without an outgoing sender e-mail, Odoo
        can block those actions while trying to notify followers by e-mail.
        """
        if (
            self._name.startswith("association.")
            and not self.env.context.get("association_allow_email_notifications")
        ):
            kwargs = dict(kwargs)
            kwargs.pop("email_layout_xmlid", None)
            kwargs.pop("partner_ids", None)
            kwargs.pop("subtype_id", None)
            kwargs["message_type"] = "comment"
            kwargs["subtype_xmlid"] = "mail.mt_note"
            self = self.with_context(
                mail_create_nosubscribe=True,
                mail_post_autofollow=False,
                mail_notify_force_send=False,
                mail_notify_noemail=True,
            )
        return super(MailThread, self).message_post(*args, **kwargs)
