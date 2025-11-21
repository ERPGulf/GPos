# Copyright (c) 2025, ERPGulf and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate
class LoyaltyPointEntryGpos(Document):
    pass

    def validate(self):
        self.set_expiry_date()

    def set_expiry_date(self):

        settings = frappe.get_single("Loyalty Point Setting")

        valid_days = settings.valid_days or 0

        if valid_days > 0:
            posting_date = getdate(self.date)

            self.expiry_date = add_days(posting_date, valid_days)

