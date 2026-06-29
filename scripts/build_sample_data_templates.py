#!/usr/bin/env python3
"""Generate sample_data/*.xlsx templates for v1.1 bulk import development and UAT."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bulk_import_service import build_xlsx_template

SAMPLE_DIR = ROOT / "sample_data"

TEMPLATES: dict[str, tuple[list[str], list]] = {
    "BOQ.xlsx": (
        ["Item No", "BOQ Code", "Description", "Specification", "Unit", "Quantity", "Rate", "Amount", "Remarks"],
        ["1", "EWC-001", "Earth work in excavation", "Ordinary soil up to 1.5m", "Cum", "100", "450", "45000", ""],
    ),
    "WBS_Template.xlsx": (
        ["WBS Code", "Parent Code", "Description", "Level", "Unit", "Planned Quantity"],
        ["1.0", "", "Civil Works", "1", "LS", "1"],
    ),
    "Labour_Master.xlsx": (
        ["Trade Code", "Trade Name", "Unit", "Standard Rate", "Category"],
        ["LAB-MASON", "Mason", "Day", "850", "Civil"],
    ),
    "Machinery_Master.xlsx": (
        ["Equipment Code", "Equipment Name", "Unit", "Hourly Rate", "Category"],
        ["MCH-EXC", "Excavator", "Hour", "2500", "Earthwork"],
    ),
    "Material_Master.xlsx": (
        ["Code", "Name", "Category", "Unit", "HSN Code", "GST %", "Reorder Level"],
        ["MAT001", "Cement OPC 53", "Civil", "Bag", "2523", "18", "100"],
    ),
    "Productivity.xlsx": (
        ["Trade", "Unit", "Output Per Hour", "Project Code", "Remarks"],
        ["Mason", "Sqm", "2.5", "PRJ-001", "Plastering"],
    ),
    "Rate_Master.xlsx": (
        ["BOQ Code", "Description", "Unit", "Labour Rate", "Machinery Rate", "Material Rate", "Total Rate"],
        ["EWC-001", "Earth work", "Cum", "120", "80", "250", "450"],
    ),
    "Customer_Master.xlsx": (
        ["Client Code", "Company Name", "Contact Person", "Client Name", "Mobile", "Email", "Address", "GST Number", "PAN Number", "Status"],
        ["CLT101", "Acme Builders Pvt Ltd", "Raj Kumar", "Acme Builders", "9876543210", "accounts@acme.in", "Mumbai", "27AABCU9603R1ZM", "AABCU9603R", "Active"],
    ),
    "Vendor_Master.xlsx": (
        ["Vendor Code", "Name", "GSTIN", "PAN", "Contact Person", "Phone", "Email", "Address", "City", "State", "Pincode"],
        ["VND101", "Steel Traders", "27AABCT1234M1Z5", "AABCT1234M", "Suresh", "9123456780", "sales@steel.in", "Industrial Area", "Pune", "Maharashtra", "411001"],
    ),
    "Employee_Master.xlsx": (
        ["Employee Code", "Name", "Department", "Designation", "Join Date", "PAN", "Phone", "Email"],
        ["EMP001", "Sample Employee", "Site", "Engineer", "2026-01-01", "", "9876500000", "emp@example.com"],
    ),
    "COA.xlsx": (
        ["Account Code", "Account Name", "Account Type", "Parent Code", "GST Applicable"],
        ["11001", "Cash in Hand", "Asset", "", "No"],
    ),
    "Opening_Balance.xlsx": (
        ["Account Code", "Debit", "Credit", "As On Date"],
        ["11001", "50000", "0", "2026-04-01"],
    ),
}


def main() -> int:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (columns, sample_row) in TEMPLATES.items():
        buf = build_xlsx_template(columns, sample_row)
        target = SAMPLE_DIR / filename
        target.write_bytes(buf.getvalue())
        print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
