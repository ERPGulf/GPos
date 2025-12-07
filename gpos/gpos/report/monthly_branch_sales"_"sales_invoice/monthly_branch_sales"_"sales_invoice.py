# # Copyright (c) 2025, ERPGulf and contributors
# # For license information, please see license.txt

# # import frappe


# def execute(filters=None):
# 	columns, data = [], []
# 	return columns, data
import frappe
from frappe.utils import getdate
from calendar import monthrange

def execute(filters=None):
    if not filters:
        filters = {}

    year = int(filters.get("year") or getdate().year)
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    # Get all POS Profiles from Sales Invoices
    pos_profiles = frappe.db.get_all(
        "Sales Invoice",
        filters={"posting_date": ["between", [start_date, end_date]], "docstatus": 1},
        fields=["DISTINCT(pos_profile) AS pos_profile"],
        pluck="pos_profile"
    )

    # Prepare columns
    columns = [{"label": "POS Profile", "fieldname": "pos_profile", "fieldtype": "Data", "width": 200}]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for i in range(1, 13):
        label = f"{month_labels[i-1]}-{str(year)[-2:]}"
        columns.append({
            "label": label,
            "fieldname": f"m{i:02}",
            "fieldtype": "Currency",
            "width": 120
        })

    # Prepare data
    data = []

    for pos in pos_profiles:
        row = {"pos_profile": pos}
        for month in range(1, 13):
            start = f"{year}-{month:02}-01"
            end = f"{year}-{month:02}-{monthrange(year, month)[1]}"

            total = frappe.db.get_value(
                "Sales Invoice",
                filters={
                    "pos_profile": pos,
                    "posting_date": ["between", [start, end]],
                    "docstatus": 1
                },
                fieldname=["SUM(grand_total)"]
            ) or 0.0

            row[f"m{month:02}"] = total

        data.append(row)

    return columns, data
