import frappe
from decimal import Decimal, getcontext, ROUND_HALF_UP

from decimal import Decimal, ROUND_HALF_UP
import frappe

TOLERANCE = Decimal("0.01")
TTL_SECONDS = 600

def lock_invoice_numbers(offline_invoice_number: str = None, unique_id: str = None):
    r = frappe.cache()

    if not offline_invoice_number and not unique_id:
        return True, None

    try:

        if offline_invoice_number:
            key1 = f"myapp:offline_invoice_cache:{offline_invoice_number}"
            added1 = r.setnx(key1, 1)

            if not added1:
                return False, f"Duplicate offline invoice number: {offline_invoice_number}"

            r.expire(key1, TTL_SECONDS)


        if unique_id:
            key2 = f"myapp:unique_id_cache:{unique_id}"
            added2 = r.setnx(key2, 1)

            if not added2:
                return False, f"Duplicate unique ID: {unique_id}"

            r.expire(key2, TTL_SECONDS)

        return True, None

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Redis Lock Error")
        return False, "Cache system error"




@frappe.whitelist(allow_guest=True)
def handle_loyalty_points(invoice_name, customer_name, mobile_no):

    try:
        invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)
        loyalty_setting = frappe.get_single("Loyalty Point Setting")

        loyalty_by_group = {}
        calculate_without_tax = loyalty_setting.get("loyalty_calculate_without_tax")


        for item in invoice_doc.items:
            loyalty_info = get_loyalty_item(item.item_code)
            if not loyalty_info or "error" in loyalty_info:
                continue


            loyalty_percentage = float(loyalty_info.get("custom_loyalty_percentage") or 0)


            if (
                loyalty_percentage == 0
                and loyalty_setting.get("loyalty_point_percentage_if_not_defined_in_item_group") == 1
            ):
                loyalty_percentage = loyalty_setting.get("loyalty_percentage")

            item_group = frappe.db.get_value("Item", item.item_code, "item_group")

            if calculate_without_tax == 1 and loyalty_percentage > 0:
                points = (loyalty_percentage / 100) * float(item.amount)
                loyalty_by_group[item_group] = loyalty_by_group.get(item_group, 0) + points

        total_loyalty_points = sum(loyalty_by_group.values())


        redeemed_points = 0
        for pay in invoice_doc.payments:
            if pay.mode_of_payment and pay.mode_of_payment.lower() in ["loyalty", "loyalty point"]:
                redeemed_points = float(pay.amount)
                break


        if total_loyalty_points > 0 or redeemed_points > 0:
            # If no mobile number, DO NOT add loyalty entry
            if not mobile_no:
                return {
                    "status": "success",
                    "earned_points": 0,
                    "redeemed_points": 0,
                    "message": "Loyalty points NOT added because no mobile number was provided."
                }


            loyalty_doc = frappe.get_doc({
                "doctype": "Loyalty Point Entry Gpos",
                "invoice_id": invoice_doc.name,
                "date": invoice_doc.posting_date,
                "total_amount": invoice_doc.grand_total,
                "custom_customer": customer_name,
                "mobile_no": mobile_no,
                "debit": total_loyalty_points if total_loyalty_points > 0 else 0,
                "credit": redeemed_points if redeemed_points > 0 else 0,
                "loyalty_point": total_loyalty_points if total_loyalty_points > 0 else None,
                "redeem_against": invoice_doc.name if redeemed_points > 0 else None,
            })
            loyalty_doc.insert(ignore_permissions=True)


            if redeemed_points > 0 and mobile_no:
                remaining_to_redeem = redeemed_points


                previous_entries = frappe.get_all(
                    "Loyalty Point Entry Gpos",
                    filters={
                        "mobile_no": mobile_no,
                        "used_loyalty_point": ["!=", 1],
                        "credit": 0
                    },
                    fields=["name", "debit"],
                    order_by="creation asc"
                )

                for entry in previous_entries:
                    if remaining_to_redeem <= 0:
                        break

                    entry_doc = frappe.get_doc("Loyalty Point Entry Gpos", entry.name)
                    available_points = float(entry_doc.debit or 0)

                    if available_points <= remaining_to_redeem:
                        remaining_to_redeem -= available_points

        return {
            "status": "success",
            "earned_points": total_loyalty_points,
            "redeemed_points": redeemed_points
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Loyalty Calculation Error")
        return {"status": "error", "message": "Loyalty calculation failed"}



@frappe.whitelist(allow_guest=True)
def get_loyalty_item(item):

    item_doc = frappe.get_all("Item", fields=["item_group"], filters={"name": item})
    if not item_doc:
        return {"error": "Item not found"}

    item_group = item_doc[0].get("item_group")
    item_group_doc = frappe.get_all(
        "Item Group",
        fields=["custom_loyalty_percentage"],
        filters={"name": item_group}
    )

    if not item_group_doc:
        frappe.log_error(frappe.get_traceback(), "Item Group not found")
        return {"error": "Item Group not found"}

    return item_group_doc[0]


@frappe.whitelist(allow_guest=True)
def handle_loyalty_points_for_return(return_invoice_name):

    try:
        return_inv = frappe.get_doc("Sales Invoice", return_invoice_name)
        if not return_inv.is_return:
            return {"status": "error", "message": "Not a return invoice."}

        original_inv = frappe.get_doc("Sales Invoice", return_inv.return_against)


        original_qty_total = sum(abs(i.qty) for i in original_inv.items)
        returned_qty_total = sum(abs(i.qty) for i in return_inv.items)

        is_full_return = (original_qty_total == returned_qty_total)


        if is_full_return:


            loyalty_entries = frappe.get_all(
                "Loyalty Point Entry Gpos",
                filters={"invoice_id": original_inv.name},
                fields=["debit", "credit"]
            )

            original_debit = 0
            original_credit = 0


            for entry in loyalty_entries:
                if entry.get("debit", 0) > 0:
                    original_debit += float(entry["debit"])
                if entry.get("credit", 0) > 0:
                    original_credit += float(entry["credit"])


            if original_debit <= 0 and original_credit <= 0:
                return {
                    "status": "success",
                    "credited_points": 0,
                    "message": "Full return but no loyalty activity found on original invoice."
                }


            loyalty_doc = frappe.get_doc({
                "doctype": "Loyalty Point Entry Gpos",
                "invoice_id": return_inv.name,
                "date": return_inv.posting_date,
                "total_amount": float(return_inv.grand_total),
                "custom_customer": return_inv.customer,
                "mobile_no": getattr(original_inv, "mobile_no", None),


                "credit": original_debit,


                "debit": original_credit,

                "loyalty_point": 0,
                "redeem_against": return_inv.name
            })
            loyalty_doc.insert(ignore_permissions=True)

            return {
                "status": "success",
                "credited_points": original_debit,
                "redeem_reversed": original_credit,
                "message": "Full loyalty reversal applied (earned + redeemed)."
            }

        total_credit_points = 0


        loyalty_settings = frappe.get_doc("Loyalty Point Setting")

        default_enabled = loyalty_settings.loyalty_point_percentage_if_not_defined_in_item_group
        default_percentage = float(loyalty_settings.loyalty_percentage or 0)

        for r_item in return_inv.items:

            item_code = r_item.item_code
            qty_returned = abs(r_item.qty)
            returned_amount = qty_returned * float(r_item.rate or 0)


            loyalty_info = get_loyalty_item(item_code)
            loyalty_percentage = float(loyalty_info.get("custom_loyalty_percentage", 0) or 0)


            if loyalty_percentage <= 0:
                if default_enabled:
                    loyalty_percentage = default_percentage
                else:
                    continue


            item_points = (returned_amount * loyalty_percentage) / 100
            total_credit_points += item_points

        total_credit_points = round(total_credit_points, 2)

        if total_credit_points <= 0:
            return {
                "status": "success",
                "credited_points": 0,
                "message": "No loyalty points applicable for partial return."
            }


        loyalty_doc = frappe.get_doc({
            "doctype": "Loyalty Point Entry Gpos",
            "invoice_id": return_inv.name,
            "date": return_inv.posting_date,
            "total_amount": float(return_inv.grand_total),
            "custom_customer": return_inv.customer,
            "mobile_no": getattr(original_inv, "custom_loyalty_customer_mobile", None),
            "debit": 0,
            "credit": total_credit_points,
            "loyalty_point": 0,
            "redeem_against": return_inv.name
        })
        loyalty_doc.insert(ignore_permissions=True)

        return {
            "status": "success",
            "credited_points": total_credit_points,
            "message": "Partial loyalty reversal applied."
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Return Loyalty Calculation Error")
        return {"status": "error", "message": "Failed to calculate loyalty for return."}