{
    "name": "Yagüven SIRCAR ↔ Payment Group Bridge",
    "version": "19.0.1.0.0",
    "summary": (
        "Auto-cálculo de retenciones IIBB SIRCAR sobre Recibos / OPs "
        "del módulo yaguven_payment_group, según las condiciones "
        "cargadas en yaguven_sircar."
    ),
    "description": """
Módulo bridge que conecta yaguven_payment_group con yaguven_sircar.

Cuando una OP está en borrador, agrega el botón "Calcular retenciones
SIRCAR" que automáticamente:

  1) Lee yaguven.sircar.partner.condition activas del partner para
     kind=retention.
  2) Por cada jurisdicción, busca el tax mapeado en
     yaguven.sircar.tax.mapping.
  3) Calcula la base imponible como neto sin IVA proporcional al
     monto pagado de las facturas imputadas.
  4) Verifica el mínimo no imponible del régimen (regime.min_amount).
     Si la base es menor, no genera línea y deja nota en chatter.
  5) Crea la línea account.payment.group.withholding con tax,
     base_amount y amount calculados.

Si ya existe una withholding line con el mismo tax cargada manualmente,
NO la pisa (respeta la edición del usuario).

Heredado solo de account.payment.group (modelo nativo de Odoo). No
extiende modelos OCA/ADHOC ni custom.
    """,
    "author": "Yagüven C.G.",
    "website": "https://yaguvencg.com.ar",
    "license": "LGPL-3",
    "category": "Accounting/Localizations/Argentina",
    "depends": [
        "account",
        "yaguven_payment_group",
        "yaguven_sircar",
    ],
    "data": [
        "views/account_payment_group_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
