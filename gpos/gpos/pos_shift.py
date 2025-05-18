import frappe
import json
import base64
import requests
from werkzeug.wrappers import Response
from datetime import datetime

@frappe.whitelist(allow_guest=True)
def parse_json_field(field):
    try:
        return json.loads(field) if isinstance(field, str) else field
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format for field: {field}")

@frappe.whitelist(allow_guest=True)
def opening_shift(period_start_date, company, user, pos_profile,name):
    """
    Function to handle POS Opening Shift operations.
    """
    try:
        payments = parse_json_field(frappe.form_dict.get("balance_details"))

        # Validate: ensure balance_details exists and is not empty
        if not payments or not isinstance(payments, list):
            return Response(
            json.dumps({"data": "Missing or invalid balance_details: must be a non-empty list."}),
            status=404,
            mimetype="application/json"
        )

        payment_items = []
        for payment in payments:
            if not payment.get("mode_of_payment"):
                return Response(
                json.dumps({"data": "Each payment entry must have a 'mode_of_payment'."}),
                status=404,
                mimetype="application/json")
            payment_items.append({
                "mode_of_payment": payment["mode_of_payment"],
                "opening_amount": float(payment.get("opening_amount", 0))
            })
        name = frappe.form_dict.get("name")    
        period_start_dt = datetime.strptime(period_start_date, "%Y-%m-%d %H:%M:%S")
        offline_user_record = frappe.get_all(
            "POS Offline Users",
            filters={"offine_username": user},
            fields=["user"],
            limit=1
        )
        if offline_user_record:
            user = offline_user_record[0].user

        # Create the POS Opening Entry only if validation passed
        doc = frappe.get_doc({
            "doctype": "POS Opening Shift",
            "name" : name,
            "period_start_date": period_start_dt,
            "company": company,
            "user": user,
            "pos_profile": pos_profile,
            "balance_details": payment_items
        })

        doc.insert(ignore_permissions=True)
        doc.submit()


        data = {
            "sync_id": doc.name,
            "period_start_date": format_datetime_safe(doc.period_start_date),
            "posting_date": format_datetime_safe(doc.posting_date),
            "company": doc.company,
            "pos_profile": doc.pos_profile,
            "user": doc.user,
            "balance_details": [
                {
                    "sync_id": p.name,
                    "mode_of_payment": p.mode_of_payment,
                    "opening_amount": p.opening_amount
                }
                for p in doc.balance_details
            ]
        }

        return Response(
            json.dumps({"data": data}),
            status=200,
            mimetype="application/json"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Opening Shift Error")

        error_response = {
            "error": "Failed to create POS Opening Shift.",
            "details": str(e)
        }

        return Response(
            json.dumps(error_response),
            status=400,
            mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def closing_shift(period_end_date,company, pos_opening_entry,name):
    try:
        payments = parse_json_field(frappe.form_dict.get("payment_reconciliation"))

        # Validate: ensure payment_reconciliation exists and is a non-empty list
        if not payments or not isinstance(payments, list):
            return Response(
                json.dumps({
                    "error": "Missing or invalid payment_reconciliation: must be a non-empty list."
                }),
                status=400,
                mimetype="application/json"
            )
        name = frappe.form_dict.get("name") 
        payment_items = []
        for payment in payments:
            if not payment.get("mode_of_payment"):
                return Response(
                    json.dumps({
                        "error": "Each payment entry must have a 'mode_of_payment'."
                    }),
                    status=400,
                    mimetype="application/json"
                )

            payment_items.append({
                "mode_of_payment": payment.get("mode_of_payment"),
                "opening_amount": float(payment.get("opening_amount", 0)),
                "expected_amount": float(payment.get("expected_amount", 0)),
                "closing_amount": float(payment.get("closing_amount", 0)),
            })

        # Fetch POS Opening Entry
        pos_opening = frappe.get_doc("POS Opening Shift", pos_opening_entry)
        if pos_opening.status != "Open":
            return Response(
                json.dumps({
                    "error": "Selected POS Opening Entry should be open."
                }),
                status=409,
                mimetype="application/json"
            )

        period_end_dt = datetime.strptime(period_end_date, "%Y-%m-%d %H:%M:%S")

        # Create POS Closing Entry
        doc = frappe.get_doc({
            "doctype": "POS Closing Shift",
            "name" : name,
            "period_end_date":period_end_dt ,
            "pos_opening_shift": pos_opening_entry,
            "company": company,
            "pos_profile": pos_opening.pos_profile,
            "user": pos_opening.user,
            "period_start_date": pos_opening.period_start_date,
            "payment_reconciliation": payment_items
        })
        doc.insert(ignore_permissions=True)
        doc.save(ignore_permissions=True)
        doc.submit()

        data = {
            "sync_id": doc.name,
            "period_start_date": format_datetime_safe(doc.period_start_date),
            "period_end_date": format_datetime_safe(doc.period_end_date),
            "posting_date": format_datetime_safe(doc.posting_date),
            # "posting_time": str(doc.posting_time),
            "pos_opening_shift": doc.pos_opening_shift,
            "company": doc.company,
            "pos_profile": doc.pos_profile,
            "user": doc.user,
            "payment_reconciliation": [
                {
                    "sync_id": p.name,
                    "mode_of_payment": p.mode_of_payment,
                    "opening_amount": p.opening_amount,
                    "expected_amount": p.expected_amount,
                    "closing_amount": p.closing_amount
                }
                for p in doc.payment_reconciliation
            ]
        }

        return Response(
            json.dumps({"data": data}),
            status=200,
            mimetype="application/json"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Closing Shift Error")

        return Response(
            json.dumps({
                "error": "An error occurred during closing shift creation.",
                "details": str(e)
            }),
            status=500,
            mimetype="application/json"
        )
from datetime import datetime, date

def format_datetime_safe(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, str):
        try:
            # Try parsing string (datetime format first, fallback to date)
            try:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(value, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return value  # fallback
    return str(value)




import frappe

@frappe.whitelist(allow_guest=True)
def get_pos_profiles_with_users():
    profiles = frappe.get_all("POS Profile", fields=["name"])
    result = []

    for profile in profiles:
        users = frappe.get_all(
            "POS Profile User",
            filters={"parent": profile.name, "parenttype": "POS Profile"},
            fields=["user"]
        )
        user_list = [u.user for u in users]
        result.append({
            "pos_profile": profile.name,
            "applicable_users": user_list
        })

    return result
