import frappe
import json
import base64
import requests
from werkzeug.wrappers import Response

@frappe.whitelist(allow_guest=True)
def parse_json_field(field):
    try:
        return json.loads(field) if isinstance(field, str) else field
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format for field: {field}")

@frappe.whitelist(allow_guest=True)
def opening_shift(period_start_date, company, user, pos_profile):
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

        # Create the POS Opening Entry only if validation passed
        doc = frappe.get_doc({
            "doctype": "POS Opening Entry",
            "period_start_date": period_start_date,
            "company": company,
            "user": user,
            "pos_profile": pos_profile,
            "balance_details": payment_items
        })

        doc.insert(ignore_permissions=True)
        doc.submit()


        data = {
            "sync_id": doc.name,
            "period_start_date": str(doc.period_start_date),
            "posting_date": str(doc.posting_date),
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
            "error": "Failed to create POS Opening Entry.",
            "details": str(e)
        }

        return Response(
            json.dumps(error_response),
            status=400,
            mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def closing_shift(period_end_date,company, pos_opening_entry):
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
        pos_opening = frappe.get_doc("POS Opening Entry", pos_opening_entry)

        # Create POS Closing Entry
        doc = frappe.get_doc({
            "doctype": "POS Closing Entry",
            "period_end_date":period_end_date ,
            "pos_opening_entry": pos_opening_entry,
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
            "period_start_date": str(doc.period_start_date),
            "period_end_date": str(doc.period_end_date),
            "posting_date": str(doc.posting_date),
            "posting_time": str(doc.posting_time),
            "pos_opening_entry": doc.pos_opening_entry,
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
