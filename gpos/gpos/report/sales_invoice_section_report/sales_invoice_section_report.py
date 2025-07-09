# # Copyright (c) 2025, ERPGulf and contributors
# # For license information, please see license.txt

# # import frappe


# # def execute(filters=None):
# # 	columns, data = [], []
# # 	return columns, data
# import frappe

# def execute(filters=None):
#     company = filters.get("company")
#     from_date = filters["from_date"]
#     to_date = filters.get("to_date")

#     # Base filter condition
#     conditions = "posting_date BETWEEN %(from_date)s AND %(to_date)s AND company = %(company)s"

#     # 1. Total Sales Invoices
#     total_invoices = frappe.db.sql("""
#         SELECT COUNT(*) FROM `tabSales Invoice`
#         WHERE {conditions}
#     """.format(conditions=conditions), filters)[0][0]

#     # 2. Status Breakdown
#     status_counts = frappe.db.sql("""
#         SELECT 
#             CASE docstatus
#                 WHEN 0 THEN 'Draft'
#                 WHEN 1 THEN 'Submitted'
#                 WHEN 2 THEN 'Cancelled'
#             END AS status,
#             COUNT(*) AS count
#         FROM `tabSales Invoice`
#         WHERE {conditions}
#         GROUP BY docstatus
#     """.format(conditions=conditions), filters, as_dict=True)

#     # 3. Total Grand Total for Submitted
#     total_submitted_amount = frappe.db.sql("""
#         SELECT SUM(grand_total) FROM `tabSales Invoice`
#         WHERE docstatus = 1 AND {conditions}
#     """.format(conditions=conditions), filters)[0][0] or 0

#     # 4. Top 5 Customers
#     top_customers = frappe.db.sql("""
#         SELECT customer, SUM(grand_total) AS total_sales
#         FROM `tabSales Invoice`
#         WHERE docstatus = 1 AND {conditions}
#         GROUP BY customer
#         ORDER BY total_sales DESC
#         LIMIT 5
#     """.format(conditions=conditions), filters, as_dict=True)

#     # 5. Invoices with Outstanding Balance
#     invoices_with_outstanding = frappe.db.sql("""
#         SELECT COUNT(*) FROM `tabSales Invoice`
#         WHERE docstatus = 1 AND outstanding_amount > 0 AND {conditions}
#     """.format(conditions=conditions), filters)[0][0]

#     # 6. Last 5 Created Invoices
#     recent_invoices = frappe.db.sql("""
#         SELECT name, posting_date, customer, grand_total
#         FROM `tabSales Invoice`
#         WHERE {conditions}
#         ORDER BY creation DESC
#         LIMIT 5
#     """.format(conditions=conditions), filters, as_dict=True)

#     # Format rows
#     data = [
#         {"label": "Total Sales Invoices", "value": total_invoices},
#         {"label": "Invoices With Outstanding", "value": invoices_with_outstanding},
#         {"label": "Total Submitted Amount", "value": total_submitted_amount}
#     ]

#     for status_row in status_counts:
#         data.append({"label": f"Invoices ({status_row.status})", "value": status_row.count})

#     data.append({"label": "", "value": ""})  # Spacer
#     data.append({"label": "Top 5 Customers by Sales", "value": ""})

#     for row in top_customers:
#         data.append({"label": row.customer, "value": row.total_sales})

#     data.append({"label": "", "value": ""})  # Spacer
#     data.append({"label": "Last 5 Created Sales Invoices", "value": ""})

#     for row in recent_invoices:
#         label = f"{row.name} ({row.customer}) - {row.posting_date}"
#         data.append({"label": label, "value": row.grand_total})

#     # Define columns
#     columns = [
#         {"label": "Metric", "fieldname": "label", "fieldtype": "Data", "width": 300},
#         {"label": "Value", "fieldname": "value", "fieldtype": "Data", "width": 200}
#     ]

#     return columns, data

import frappe
from datetime import datetime, timedelta

def execute(filters=None):
    filters = filters or {}

    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    company = filters.get("company")

    if not (from_date and to_date and company):
        frappe.throw("Please select Company, From Date, and To Date")

    # Get unique POS Profiles used in the date range
    pos_profiles = frappe.db.sql("""
        SELECT DISTINCT pos_profile
        FROM `tabSales Invoice`
        WHERE company = %(company)s
        AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        AND docstatus = 1
        AND pos_profile IS NOT NULL
    """, filters, as_dict=True)

    pos_list = [row.pos_profile for row in pos_profiles]

    # Build a list of all dates in range
    start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    date_range = [(start_date + timedelta(days=i)).isoformat() for i in range((end_date - start_date).days + 1)]

    # Fetch sales totals per date and pos_profile
    sales_data = frappe.db.sql("""
        SELECT posting_date, pos_profile, SUM(grand_total) AS total
        FROM `tabSales Invoice`
        WHERE company = %(company)s
        AND docstatus = 1
        AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY posting_date, pos_profile
    """, filters, as_dict=True)

    # Organize results into a nested dict: sales_map[date][pos_profile] = total
    sales_map = {}
    for row in sales_data:
        date = row.posting_date.strftime("%Y-%m-%d")
        sales_map.setdefault(date, {})[row.pos_profile] = row.total

    # Build table rows
    data = []
    for date in date_range:
        row = {"date": date}
        total_sales = 0
        for pos in pos_list:
            value = sales_map.get(date, {}).get(pos, 0)
            row[pos] = value
            total_sales += value
        row["total_sales"] = total_sales
        data.append(row)

    # Build columns: Date, Total Sales, POS Profiles
    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": "Total Sales", "fieldname": "total_sales", "fieldtype": "Currency", "width": 130}
    ] + [
        {"label": pos, "fieldname": pos, "fieldtype": "Currency", "width": 130}
        for pos in pos_list
    ]

    return columns, data
