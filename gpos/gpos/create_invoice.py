import frappe
from werkzeug.wrappers import Response
import csv
import json
from io import StringIO
from datetime import datetime
from collections import defaultdict

@frappe.whitelist(allow_guest=True)
def create_invoices_using_csv():

    if frappe.request.method != "POST":
        return Response(
            json.dumps({"data": "Only POST requests are allowed."}),
            status=404, mimetype='application/json'
        )

    uploaded_file = frappe.request.files.get("file")
    image_files = frappe.request.files.getlist("images")

    if not uploaded_file:
        return Response(
            json.dumps({"data": "No CSV file uploaded."}),
            status=404, mimetype='application/json'
        )
    if not uploaded_file.filename.endswith('.csv'):
        return Response(
            json.dumps({"data": "Uploaded file must be a CSV."}),
            status=404, mimetype='application/json'
        )
    if not image_files:
        return Response(
            json.dumps({"data": "No image files uploaded."}),
            status=404, mimetype='application/json'
        )

    gpos_settings = frappe.get_doc("pos setting")
    post_to_pos_invoice = gpos_settings.get("post_to_pos_invoice")
    post_to_sales_invoice = gpos_settings.get("post_to_sales_invoice")


    if not (post_to_pos_invoice or post_to_sales_invoice):
        return Response(
            json.dumps({"data":"No invoice type selected in GPOS Settings."}),
            status=404, mimetype='application/json'
        )

    file_content = uploaded_file.read().decode("utf-8")
    csv_data = list(csv.DictReader(StringIO(file_content)))
    image_map = {img.filename: img for img in image_files}

    invoices_data = defaultdict(lambda: {"items": [], "details": {},"taxes": []})
    invoices_created = []
    current_invoice_id = None

    for row_num, row in enumerate(csv_data, start=1):
        customer = row.get("Customer")
        invoice_id = row.get("ID")

        if invoice_id:
            invoices_data[invoice_id]["details"] = {
                "customer": customer,
                "company": row.get("Company"),
                "posting_date": row.get("Date"),
                "currency": row.get("Currency", "USD"),
                "exchange_rate": row.get("Exchange Rate", "1"),
                "due_date": datetime.strptime(
                    row.get("Due Date (Payment Schedule)", datetime.today().strftime("%m/%d/%Y")),
                    "%m/%d/%Y"
                ).strftime("%Y-%m-%d"),
                "attachment": row.get("Attachments"),
                "custom_unique_id": row.get("unique_id"),
                "custom_zatca_pos_name": row.get("zatca_pos_name")


            }

            item = {
                "item_code": row.get("Item Name (Items)"),
                "qty": float(row.get("UOM Conversion Factor (Items)", "1")),
                "rate": float(row.get("Rate (Items)", "0")),
                "uom": row.get("UOM (Items)", "Nos"),
                "cost_center": row.get("Cost Center (Items)"),
                "income_account": row.get("Income Account (Items)"),
                "amount": float(row.get("Amount (Items)", "0")),
            }
            invoices_data[invoice_id]["items"].append(item)
            current_invoice_id = invoice_id
            tax = {
            "charge_type": row.get("Tax Type"),
            "account_head": row.get("Tax Account Head"),
            "description": row.get("Description"),
            "tax_rate": float(row.get("Tax Rate", "0") or "0"),
            "amount": float(row.get("Tax Amount", "0") or "0"),
        }
            invoices_data[invoice_id]["taxes"].append(tax)
        else:
            if current_invoice_id:
                item = {
                    "item_code": row.get("Item Name (Items)"),
                    "qty": float(row.get("UOM Conversion Factor (Items)", "1")),
                    "rate": float(row.get("Rate (Items)", "0")),
                    "uom": row.get("UOM (Items)", "Nos"),
                    "cost_center": row.get("Cost Center (Items)"),
                    "income_account": row.get("Income Account (Items)"),
                    "amount": float(row.get("Amount (Items)", "0")),
                }
                invoices_data[current_invoice_id]["items"].append(item)
            else:
                return Response(
                    json.dumps({"data": f"Skipping row {row_num} due to missing Invoice ID."}),
                    status=404, mimetype='application/json'
                )

    for invoice_id, data in invoices_data.items():
        details = data["details"]
        invoice_type = "POS Invoice" if post_to_pos_invoice else "Sales Invoice"
        if post_to_pos_invoice or post_to_sales_invoice:
            existing_invoice = frappe.get_all(
                invoice_type,  # "POS Invoice" or "Sales Invoice"
                ["name"],
                filters={'custom_unique_id': ['like', details["custom_unique_id"]]}
            )
            if existing_invoice:
                return Response(
                    json.dumps({
                        "data": f"A duplicate entry was detected for unique ID '{details['custom_unique_id']}'. Invoice '{existing_invoice[0]['name']}' already exists."
                    }),
                    status=409,
                    mimetype='application/json'
                )

        total_tax_amount = sum(tax["amount"] for tax in data["taxes"])
        total_item_amount = sum(item["amount"] for item in data["items"])
        grand_total = total_item_amount + total_tax_amount

        invoice_doc = {
            "doctype": invoice_type,
            "customer": details["customer"],
            "company": details["company"],
            "posting_date": details["posting_date"],
            "currency": details["currency"],
            "exchange_rate": details["exchange_rate"],
            "due_date": details["due_date"],
            "custom_unique_id": details["custom_unique_id"],
            "custom_zatca_pos_name": details["custom_zatca_pos_name"],
            "items": data["items"],
            "taxes": data["taxes"],
            "total": grand_total
        }

        if invoice_type == "POS Invoice":
            default_mode_of_payment = "Cash"
            total_amount = sum(item.get("amount", 0) for item in data["items"])
            invoice_doc["payments"] = [
                {
                    "mode_of_payment": default_mode_of_payment,
                    "amount": total_amount,
                }
            ]

        new_invoice = frappe.get_doc(invoice_doc)
        new_invoice.insert(ignore_permissions=True)
        new_invoice.submit()
        invoices_created.append(new_invoice.name)

        attachment_file_name = details.get("attachment")
        if attachment_file_name and attachment_file_name in image_map:
            image_content = image_map[attachment_file_name].read()
            file_doc = frappe.get_doc({
                "doctype": "File",
                "file_name": attachment_file_name,
                "attached_to_doctype": invoice_type,
                "attached_to_name": new_invoice.name,
                "content": image_content,
            })
            file_doc.save(ignore_permissions=True)

    return {
        "message": f"{len(invoices_created)} {invoice_type}s created successfully.",
        "invoices": invoices_created
    }