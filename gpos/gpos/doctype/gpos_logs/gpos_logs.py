# Copyright (c) 2025, ERPGulf and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, nowdate
from frappe.model.document import Document


class gposlogs(Document):
	pass


@frappe.whitelist()
def delete_old_gpos_logs():
	cutoff_date = add_days(nowdate(), -10)

	old_logs = frappe.get_all(
		"gpos logs",
		filters={"creation": ["<", cutoff_date]},
		pluck="name",
	)

	for log in old_logs:
		frappe.delete_doc("gpos logs", log, ignore_permissions=True)

	frappe.db.commit()

	frappe.response["message"] = f"{len(old_logs)} log(s) older than 10 days deleted successfully."
