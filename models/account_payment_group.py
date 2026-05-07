"""Auto-cálculo de retenciones SIRCAR sobre OP / Recibo del custom
yaguven_payment_group.

Hereda solo `account.payment.group` (modelo nativo Odoo Enterprise);
los modelos del custom yaguven_payment_group y de yaguven_sircar se
leen sin extender, como datasource.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import html_escape
from markupsafe import Markup


class AccountPaymentGroup(models.Model):
    _inherit = "account.payment.group"

    sircar_retentions_computed = fields.Boolean(
        string="Retenciones SIRCAR calculadas",
        default=False,
        copy=False,
        help="Indica si ya se ejecutó el cálculo automático de "
             "retenciones SIRCAR sobre esta OP. Permite que el botón "
             "se muestre solo cuando aún no se calcularon.",
    )

    def action_compute_sircar_retentions(self):
        """Calcula las retenciones SIRCAR aplicables al partner de
        esta OP y crea las líneas de withholding correspondientes."""
        for group in self:
            group._compute_sircar_retentions()
        return True

    def _compute_sircar_retentions(self):
        self.ensure_one()
        if self.partner_type != "supplier":
            raise UserError(_(
                "Las retenciones SIRCAR aplican solo a OPs de proveedor."
            ))
        if self.state != "draft":
            raise UserError(_(
                "La OP debe estar en borrador para calcular retenciones."
            ))

        Cond = self.env["yaguven.sircar.partner.condition"]
        Mapping = self.env["yaguven.sircar.tax.mapping"]
        WH = self.env["account.payment.group.withholding"]

        partner = self.partner_id.commercial_partner_id
        conditions = Cond.search([
            ("partner_id", "=", partner.id),
            ("kind", "=", "retention"),
            ("active", "=", True),
        ])
        if not conditions:
            self._sircar_log(
                _("Sin condiciones SIRCAR cargadas para %s. "
                  "No se calcula retención.") % partner.name
            )
            self.sircar_retentions_computed = True
            return

        base_neto = self._sircar_compute_base_neto()
        for cond in conditions:
            mapping = Mapping.search([
                ("company_id", "=", self.company_id.id),
                ("regime_id.jurisdiction_id", "=",
                 cond.jurisdiction_id.id),
                ("kind", "=", "retention"),
                ("active", "=", True),
            ], limit=1)
            if not mapping:
                self._sircar_log(_(
                    "Sin tax mapeado para %s · retención. "
                    "Cargar mapping en SIRCAR > Mapping Impuestos."
                ) % cond.jurisdiction_id.name)
                continue
            tax = mapping.tax_id
            if not tax.amount or tax.amount <= 0:
                self._sircar_log(_(
                    "El tax %s no tiene alícuota positiva — no se calcula "
                    "retención para %s."
                ) % (tax.name, cond.jurisdiction_id.name))
                continue

            existing = self.withholding_ids.filtered(
                lambda w: w.tax_id == tax
            )
            if existing:
                self._sircar_log(_(
                    "Retención %s ya cargada manualmente; respeto valor "
                    "existente y no recalculo."
                ) % tax.name)
                continue

            min_amount = cond.regime_id.min_amount or 0.0
            if min_amount and base_neto < min_amount:
                self._sircar_log(_(
                    "Retención %s NO aplicada: base $%(base).2f < mínimo "
                    "no imponible $%(min).2f del régimen %(reg)s."
                ) % {
                    "base": base_neto, "min": min_amount,
                    "reg": cond.regime_id.code,
                })
                continue

            amount = round(base_neto * tax.amount / 100.0, 2)
            WH.create({
                "payment_group_id": self.id,
                "tax_id": tax.id,
                "base_amount": base_neto,
                "amount": amount,
            })
            self._sircar_log(_(
                "Retención SIRCAR autocalculada: %(tax)s · base "
                "$%(base).2f × %(rate)s%% = $%(amt).2f · régimen "
                "%(reg)s · %(jur)s"
            ) % {
                "tax": tax.name, "base": base_neto,
                "rate": tax.amount, "amt": amount,
                "reg": cond.regime_id.code,
                "jur": cond.jurisdiction_id.name,
            })

        self.sircar_retentions_computed = True

    def _sircar_compute_base_neto(self):
        """Calcula la base imponible sin IVA proporcional al monto pagado.

        - Suma `amount_total` (bruto) y `amount_untaxed` (neto) de las
          facturas imputadas en `to_pay_move_line_ids`.
        - Calcula ratio = to_pay_amount / total_bruto_facturas (cap 1).
        - Devuelve neto_total × ratio.

        Si no hay facturas imputadas (anticipo puro), devuelve 0 — los
        anticipos no tienen base imponible separada.
        """
        self.ensure_one()
        total_bruto = 0.0
        total_neto = 0.0
        for line in self.to_pay_move_line_ids:
            move = line.move_id
            if move.move_type not in ("in_invoice", "in_refund"):
                continue
            sign = 1 if move.move_type == "in_invoice" else -1
            total_bruto += sign * move.amount_total
            total_neto += sign * move.amount_untaxed
        if total_bruto <= 0:
            return 0.0
        pagado_bruto = self.to_pay_amount or 0.0
        ratio = min(pagado_bruto / total_bruto, 1.0)
        return round(total_neto * ratio, 2)

    def _sircar_log(self, message):
        self.ensure_one()
        body = (
            "<p><strong>SIRCAR — Cálculo de retenciones</strong></p>"
            "<p>%s</p>" % html_escape(message)
        )
        self.message_post(
            body=Markup(body),
            subject=_("SIRCAR — Retenciones"),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
