# Copyright (c) 2025, ERPGulf and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class promotion(Document):
	pass





@frappe.whitelist()
def get_item_price(item_code,price_list,uom=None):
    try:
        filters = {"item_code": item_code, "price_list": price_list}
        if uom:
            filters["uom"] = uom
        price = frappe.db.get_value(
            "Item Price",
            filters,
            "price_list_rate"
        )
        return {"price": float(price or 0)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Item Price Fetch Error")
        return {"error": str(e), "price": 0}


# Calculate Discount
@frappe.whitelist()
def calculate_price_after_discount(sale_price, discount_type=None, discount_percentage=None, discount__amount=None):
    try:
        sale_price = float(sale_price or 0)
        discount_percentage = float(discount_percentage or 0)
        discount_amount = float(discount__amount or 0)
        price_after_discount = sale_price

        if discount_type == "Discount Percentage":
            price_after_discount = sale_price - (sale_price * discount_percentage / 100)

        else:
            price_after_discount = sale_price - discount_amount


        return {"price_after_discount": price_after_discount}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Discount Calculation Error")
        return {"error": str(e), "price_after_discount": 0}


@frappe.whitelist(allow_guest=True)
def get_valuation_rate(itemcode, uom=None):
    try:
        filters = {"item_code": itemcode}
        if uom:
            filters["stock_uom"] = uom
        valuation_rate = frappe.db.get_value("Bin",
            filters,
            "valuation_rate"
        )
        return valuation_rate
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Valuation Rate Fetch Error")
        return None
