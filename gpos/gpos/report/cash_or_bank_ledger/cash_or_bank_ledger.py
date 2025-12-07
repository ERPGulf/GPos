# # Copyright (c) 2025, ERPGulf and contributors
# # For license information, please see license.txt

# # import frappe


# def execute(filters=None):
# 	columns, data = [], []
# 	return columns, data
import frappe
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}

    account = filters.get("account")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    # Get opening balance
    opening_balance = frappe.db.sql("""
        SELECT 
            SUM(debit) - SUM(credit) 
        FROM `tabGL Entry`
        WHERE account = %s AND posting_date < %s AND docstatus = 1
    """, (account, from_date))[0][0] or 0.0

    # Prepare columns
    columns = [
        {"label": "Voucher No", "fieldname": "voucher_no", "fieldtype": "Data", "width": 120},
        {"label": "Description", "fieldname": "remarks", "fieldtype": "Data", "width": 200},
        {"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 100},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 100},
        {"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 120},
    ]

    # Fetch GL Entries
    entries = frappe.db.sql("""
        SELECT
            posting_date, debit, credit, voucher_no, remarks
        FROM `tabGL Entry`
        WHERE account = %s
          AND posting_date BETWEEN %s AND %s
          AND docstatus = 1
        ORDER BY posting_date ASC
    """, (account, from_date, to_date), as_dict=1)

    # Compute running balance
    data = []
    balance = opening_balance
    for entry in entries:
        balance += flt(entry.debit) - flt(entry.credit)
        entry["balance"] = balance
        data.append(entry)

    return columns, data
