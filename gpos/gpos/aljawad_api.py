import requests
import json
import frappe
import json
import urllib.parse
import base64
from werkzeug.wrappers import Response
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password
from frappe.utils.image import optimize_image
from mimetypes import guess_type
from frappe.utils import now_datetime, cint
from datetime import datetime, timedelta


@frappe.whitelist(allow_guest=True)
def get_promotion_list(pos_profile):

    try:

        if not frappe.db.exists("POS Profile", pos_profile):
            return Response(
                json.dumps({"error": "POS Profile not found"}),
                status=404,
                mimetype="application/json",
            )

        today = datetime.today().date()

        promotions = frappe.get_all(
            "promotion",
            filters={"valid_upto": (">=", today)},
            fields=["name", "company", "valid_from", "valid_upto"],
        )

        result = []
        linked_to_any_promotion = False

        for promo in promotions:
            doc = frappe.get_doc("promotion", promo.name)
            pos_profiles = [row.pos_profile for row in doc.pos_profile_table]

            if pos_profile not in pos_profiles:
                continue

            linked_to_any_promotion = True

            item_table = [
                {
                    "id": item.name,
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "discount_type": (
                        "PERCENTAGE"
                        if item.discount_type == "Discount Percentage"
                        else (
                            "AMOUNT"
                            if item.discount_type == "Discount Amount"
                            else (
                                "RATE"
                                if item.discount_type == "Rate"
                                else item.discount_type
                            )
                        )
                    ),
                    "min_qty": item.min_qty,
                    "max_qty": item.max_qty,
                    "discount_percentage": item.discount_percentage,
                    "discount_price": item.discount__amount,
                    "rate": item.rate,
                }
                for item in doc.item_table
            ]

            profile_doc = frappe.get_doc("POS Profile", pos_profile)

            result.append(
                {
                    "id": doc.name,
                    "company": doc.company,
                    "disabled": profile_doc.disabled,
                    "valid_from": str(doc.valid_from),
                    "valid_upto": str(doc.valid_upto),
                    "items": item_table,
                }
            )

        if not linked_to_any_promotion:
            return Response(
                json.dumps(
                    {"error": "This POS Profile is not linked to any promotions"}
                ),
                status=404,
                mimetype="application/json",
            )

        return Response(
            json.dumps({"data": result}, default=str),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )
