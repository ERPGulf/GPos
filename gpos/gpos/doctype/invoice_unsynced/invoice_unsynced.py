# Copyright (c) 2025, ERPGulf and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InvoiceUnsynced(Document):
	pass


@frappe.whitelist()
def update_invoice_unsynced_status():
	updated = 0

	invoices = frappe.get_all(
		"Invoice Unsynced",
		filters={"clearing_status": 0},
		fields=["name", "invoice_number"]  # Replace with your actual fieldname if different
	)

	for inv in invoices:
		if not inv.invoice_number:
			continue

		sales_invoice = frappe.db.exists(
			"Sales Invoice",
			{
				"custom_offline_invoice_number": inv.invoice_number,
				"docstatus": 1
			}
		)

		if sales_invoice:
			frappe.db.set_value(
				"Invoice Unsynced",
				inv.name,
				"clearing_status",
				1,
				update_modified=False
			)
			updated += 1

	frappe.db.commit()

	frappe.response["message"] = f"{updated} invoice(s) updated successfully."
