"""UI registry for bulk import modules — labels, categories, implementation status."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportModuleInfo:
    key: str
    label: str
    category: str
    description: str
    implemented: bool = True
    requires_project: bool = False
    bulk_api_key: str | None = None


IMPORT_MODULE_CATALOG: list[ImportModuleInfo] = [
    ImportModuleInfo("boq", "BOQ Line Items", "BOQ",
                     "Import BOQ lines for a project (creates BOQ master + workflow).",
                     True, True, "boq"),
    ImportModuleInfo("boq_library", "Standard BOQ Library", "BOQ",
                     "Maintain reusable BOQ catalogue items.", True, False, None),
    ImportModuleInfo("customers", "Customer Master", "Accounts Opening",
                     "Import client / customer records.", True, False, "customers"),
    ImportModuleInfo("vendors", "Vendor Master", "Accounts Opening",
                     "Import supplier / vendor records.", True, False, "vendors"),
    ImportModuleInfo("materials", "Material Master", "Accounts Opening",
                     "Import materials (also on Store → Materials).", True, False, "materials"),
    ImportModuleInfo("employees", "Employee Master", "Accounts Opening",
                     "Employee import template + validation.", False, False, "employees"),
    ImportModuleInfo("coa", "Chart of Accounts", "Accounts Opening",
                     "Ledger / COA template.", False, False, "coa"),
    ImportModuleInfo("opening_balances", "Opening Balance", "Accounts Opening",
                     "Opening balance entries.", False, False, "opening_balances"),
    ImportModuleInfo("bank_accounts", "Bank Accounts", "Accounts Opening",
                     "Bank account master.", False, False, "bank_accounts"),
    ImportModuleInfo("sales_invoice", "Sales Invoice", "Sales", "Sales invoice import.", False),
    ImportModuleInfo("sales_receipt", "Sales Receipt", "Sales", "Customer receipt import.", False),
    ImportModuleInfo("credit_note", "Credit Note", "Sales", "Credit note import.", False),
    ImportModuleInfo("debit_note", "Debit Note", "Sales", "Debit note import.", False),
    ImportModuleInfo("purchase_invoice", "Purchase Invoice", "Purchase", "Purchase invoice import.", False),
    ImportModuleInfo("purchase_order", "Purchase Order", "Purchase", "PO import.", False),
    ImportModuleInfo("grn", "GRN", "Purchase", "Goods receipt import.", False),
    ImportModuleInfo("purchase_payment", "Purchase Payment", "Purchase", "Supplier payment import.", False),
    ImportModuleInfo("customer_receipts", "Customer Receipts", "Payment", "Receipt voucher import.", False),
    ImportModuleInfo("supplier_payments", "Supplier Payments", "Payment", "Payment voucher import.", False),
    ImportModuleInfo("cash_payments", "Cash Payments", "Payment", "Cash payment import.", False),
    ImportModuleInfo("journal_entries", "Journal Entries", "Payment", "Journal voucher import.", False),
    ImportModuleInfo("contra_entries", "Contra Entries", "Payment", "Contra / transfer import.", False),
    ImportModuleInfo("bank_statement", "Bank Transactions", "Bank",
                     "Bank statement lines for reconciliation.", False, False, "bank_statement"),
]


def get_module_info(key: str) -> ImportModuleInfo | None:
    return next((m for m in IMPORT_MODULE_CATALOG if m.key == key), None)


def modules_by_category() -> dict[str, list[ImportModuleInfo]]:
    grouped: dict[str, list[ImportModuleInfo]] = {}
    for mod in IMPORT_MODULE_CATALOG:
        grouped.setdefault(mod.category, []).append(mod)
    for items in grouped.values():
        items.sort(key=lambda m: m.label)
    return grouped
