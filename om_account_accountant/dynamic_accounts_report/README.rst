Dynamic Accounting Reports for Odoo 20
======================================

Integrated companion of ``om_account_accountant``. It supplies ten interactive
reports with filters, comparisons, entry drill-down, PDF and XLSX exports.
Financial statement trees and posted tax calculations use ``accounting_pdf_reports``.
Aging reconstructs residual balances at the selected date through partial reconciliations.

The report menus keep their original external ids and positions. Their Advanced
options button opens the original report wizard, preserving localized tax grids,
tax closing, financial statement configuration and other specialized options.
Combined Aging remains a distinct advanced report. Unique reports are unchanged.

No dependency on base_accounting_kit, base_account_budget or cybrosys_support_client.
The original downloaded source is retained in the project's pre-integration backup.
This integration replaces its incompatible frontend and defective calculations.
Source copyright and LGPL notices in the original archive are preserved.

Install or upgrade the main accounting app. For command-line maintenance, update
both om_account_accountant and dynamic_accounts_report; the main app's Apps upgrade
button includes installed suite companions automatically.
