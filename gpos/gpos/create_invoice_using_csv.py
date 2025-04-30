
import frappe
from frappe.utils.file_manager import save_file
from werkzeug.wrappers import Response
import csv
import json
import os
from io import StringIO
from datetime import datetime
from collections import defaultdict
import pandas as pd


@frappe.whitelist(allow_guest=True)
def create_invoices_csv():
    if frappe.request.method != "POST":
        return Response(
            json.dumps({"data": "Only POST requests are allowed."}),
            status=404, mimetype='application/json'
        )

    uploaded_file = frappe.request.files.get("file")

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

    file_content = uploaded_file.read().decode("utf-8")
    csv_data = list(csv.DictReader(StringIO(file_content)))

    invoices_data = defaultdict(lambda: {"items": [], "details": {}, "taxes": []})
    invoices_created = []
    current_invoice_id = None

    for row_num, row in enumerate(csv_data, start=1):
        customer = row.get("Customer")
        invoice_id = row.get("ID")

        if invoice_id:
            invoices_data[invoice_id]["details"] = {
                "customer": customer,
                "company":row.get("Company"),
                "posting_date":datetime.now().strftime("%Y-%m-%d"),
                "currency": row.get("Currency", "USD"),
                "exchange_rate": row.get("Exchange Rate", "1"),
                "due_date" : datetime.now().strftime("%Y-%m-%d")
            }

            item_tax_template = row.get("Item Tax Template")
            tax_details_from_template = []

            if item_tax_template:
                try:
                    template_doc = frappe.get_doc("Item Tax Template", item_tax_template)
                    for tax in template_doc.taxes:
                        item_amount = int(row.get("Amount (Items)", "0"))
                        tax_amount = (tax.tax_rate / 100) * item_amount if item_amount else 0

                        tax_details_from_template.append({
                            "charge_type": "On Net Total",
                            "account_head": row.get("Tax Account Head") or tax.account_head,
                            "description": row.get("Description") or tax.description,
                            "rate": tax.tax_rate,
                            "amount": tax_amount
                        })
                except frappe.DoesNotExistError:
                    return Response(
                        json.dumps({"data": f"Item Tax Template '{item_tax_template}' not found for row {row_num}."}),
                        status=404, mimetype='application/json'
                    )

            item = {
                "item_code": row.get("Item Name (Items)"),
                "qty": float(row.get("UOM Conversion Factor (Items)", "1") or "1"),
                "rate": float(row.get("Rate (Items)", "0") or "0"),
                "uom": row.get("UOM (Items)", "Nos"),
                "amount": float(row.get("Amount (Items)", "0") or "0"),
                "item_tax_template": item_tax_template,
            }
            invoices_data[invoice_id]["items"].append(item)
            invoices_data[invoice_id]["taxes"].extend(tax_details_from_template)
            current_invoice_id = invoice_id

        else:
            if current_invoice_id:
                item = {
                    "item_code": row.get("Item Name (Items)"),
                    "qty": float(row.get("UOM Conversion Factor (Items)", "1") or "1"),
                    "rate": float(row.get("Rate (Items)", "0") or "0"),
                    "uom": row.get("UOM (Items)", "Nos"),
                    "amount": float(row.get("Amount (Items)", "0") or "0"),
                    "item_tax_template": row.get("Item Tax Template"),
                }
                invoices_data[current_invoice_id]["items"].append(item)
            else:
                return Response(
                    json.dumps({"data": f"Skipping row {row_num} due to missing Invoice ID."}),
                    status=404, mimetype='application/json'
                )

    for invoice_id, data in invoices_data.items():
        details = data["details"]
        company = details["company"]
        if not company:
            return Response(
                json.dumps({"data": f"Missing company for invoice ID {invoice_id}."}),
                status=404, mimetype='application/json'
            )

        company_settings = frappe.get_doc("Company", company)
        post_to_pos_invoice = company_settings.get("custom_post_to_pos_invoice") == 1
        post_to_sales_invoice = company_settings.get("custom_post_to_pos_invoice") != 1

        invoice_type = "POS Invoice" if post_to_pos_invoice else "Sales Invoice"
        total_tax_amount = sum(tax["amount"] for tax in data["taxes"])
        total_item_amount = sum(item["amount"] for item in data["items"])
        grand_total = total_item_amount + total_tax_amount
        invoice_doc = {
            "doctype": invoice_type,
            "customer": details["customer"],
            "company": company,
            "posting_date": details["posting_date"],
            "currency": details["currency"],
            "exchange_rate": details["exchange_rate"],
            "due_date": details["due_date"],
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
        new_invoice.save()

        if invoice_type == "POS Invoice":
            new_invoice.submit()

        invoices_created.append(new_invoice.name)

    return {
        "message": f"{len(invoices_created)} invoices created successfully.",
        "invoices": invoices_created
    }


@frappe.whitelist(allow_guest=True)
def create_invoice_and_generate_csv():
    if frappe.request.method != "POST":
        return Response(json.dumps({"data": "Only POST requests are allowed."}),
                        status=404, mimetype='application/json')

    uploaded_file = frappe.request.files.get("file")
    if not uploaded_file:
        return Response(json.dumps({"data": "No CSV file uploaded."}),
                        status=404, mimetype='application/json')
    if not uploaded_file.filename.endswith('.csv'):
        return Response(json.dumps({"data": "Uploaded file must be a CSV."}),
                        status=404, mimetype='application/json')

    file_content = uploaded_file.read().decode("utf-8")
    csv_reader = csv.DictReader(StringIO(file_content))
    original_fieldnames = csv_reader.fieldnames
    csv_data = list(csv_reader)

    invoices_data = defaultdict(lambda: {"items": [], "details": {}, "taxes": []})
    invoices_created = []
    new_csv_data = []

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
                "due_date":row.get("Due Date"),
            }

            item_tax_template = row.get("Item Tax Template")
            tax_details_from_template = []

            if item_tax_template:
                try:
                    template_doc = frappe.get_doc("Item Tax Template", item_tax_template)
                    for tax in template_doc.taxes:
                        item_amount = int(row.get("Amount (Items)", "0"))
                        tax_amount = (tax.tax_rate / 100) * item_amount if item_amount else 0

                        tax_details_from_template.append({
                            "charge_type": "On Net Total",
                            "account_head": row.get("Tax Account Head") or tax.account_head,
                            "description": row.get("Description") or tax.description,
                            "rate": tax.tax_rate,
                            "amount": tax_amount
                        })
                except frappe.DoesNotExistError:
                    return Response(
                        json.dumps({"data": f"Item Tax Template '{item_tax_template}' not found for row {row_num}."}),
                        status=404, mimetype='application/json'
                    )

            item = {
                "item_code": row.get("Item Name (Items)"),
                "qty": float(row.get("UOM Conversion Factor (Items)", "1") or "1"),
                "rate": float(row.get("Rate (Items)", "0") or "0"),
                "uom": row.get("UOM (Items)", "Nos"),
                "amount": float(row.get("Amount (Items)", "0") or "0"),
                "item_tax_template": item_tax_template,
            }
            invoices_data[invoice_id]["items"].append(item)
            invoices_data[invoice_id]["taxes"].extend(tax_details_from_template)
            current_invoice_id = invoice_id

        else:
            if current_invoice_id:
                item = {
                    "item_code": row.get("Item Name (Items)"),
                    "qty": float(row.get("UOM Conversion Factor (Items)", "1") or "1"),
                    "rate": float(row.get("Rate (Items)", "0") or "0"),
                    "uom": row.get("UOM (Items)", "Nos"),
                    "amount": float(row.get("Amount (Items)", "0") or "0"),
                    "item_tax_template": row.get("Item Tax Template"),
                }
                invoices_data[current_invoice_id]["items"].append(item)
            else:
                return Response(
                    json.dumps({"data": f"Skipping row {row_num} due to missing Invoice ID."}),
                    status=404, mimetype='application/json'
                )



        for invoice_id, data in invoices_data.items():
            details = data["details"]
            company = details["company"]
            if not company:
                return Response(json.dumps({"data": f"Missing company for invoice ID {invoice_id}."}),
                                status=404, mimetype='application/json')

            company_settings = frappe.get_doc("Company", company)
            is_pos_invoice = company_settings.get("custom_post_to_pos_invoice") == 1
            invoice_type = "POS Invoice" if is_pos_invoice else "Sales Invoice"
        zimra_submit=frappe.form_dict.get("zimra_submit")
        if zimra_submit and invoice_type=="Sales Invoice":
            for invoice_id in invoices_data.keys():
                try:
                    invoice_doc = frappe.get_doc("Sales Invoice", invoice_id)
                    qr_data = invoice_doc.get("custom_qr_string_data", "No QR Data")
                    zimra_response = invoice_doc.get("custom_zimra_response", "No Response")
                except frappe.DoesNotExistError:
                    return Response(json.dumps({"data": f"Invoice ID {invoice_id} not found."}),
                                    status=404, mimetype='application/json')

                for row in csv_data:
                    row["Qr String Data"] = f"QR Code Data: {qr_data}"
                    row["Response"] = f"Response: {zimra_response}"
                    new_csv_data.append(row)

            output = StringIO()
            fieldnames = original_fieldnames + ["Qr String Data", "Response"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_csv_data)

            file_content = output.getvalue()
            file_name = "processed_invoices.csv"
            saved_file = save_file(file_name, file_content, "File", "Processed_Invoices", is_private=0)

            return Response(json.dumps({"file_url": saved_file.file_url}),
                            status=200, mimetype='application/json')


    for invoice_id, data in invoices_data.items():
        details = data["details"]
        company = details["company"]
        if not company:
            return Response(json.dumps({"data": f"Missing company for invoice ID {invoice_id}."}),
                            status=404, mimetype='application/json')

        company_settings = frappe.get_doc("Company", company)
        is_pos_invoice = company_settings.get("custom_post_to_pos_invoice") == 1
        invoice_type = "POS Invoice" if is_pos_invoice else "Sales Invoice"

        invoice_doc = {
            "doctype": invoice_type,
            "customer": details["customer"],
            "company": company,
            "posting_date": details["posting_date"],
            "currency": details["currency"],
            "exchange_rate": details["exchange_rate"],
            "due_date": details["due_date"],
            "items": data["items"],
            "taxes": data["taxes"],
            "total": sum(item["amount"] for item in data["items"])
        }

        if is_pos_invoice:
            invoice_doc["payments"] = [{
                "mode_of_payment": "Cash",
                "amount": sum(item["amount"] for item in data["items"]),
            }]

        new_invoice = frappe.get_doc(invoice_doc)
        new_invoice.insert(ignore_permissions=True)
        new_invoice.save()

        if is_pos_invoice:
            new_invoice.submit()
            invoices_created.append(new_invoice.name)

        if is_pos_invoice or zimra_submit:
            invoice_doc_fetched = frappe.get_doc(invoice_type, new_invoice.name)
            for row in csv_data:
                qr_data = invoice_doc_fetched.get("custom_qr_string_data")
                row["Qr String Data"] = f"QR Code Data: {qr_data}"
                new_csv_data.append(row)



            output = StringIO()
            fieldnames = original_fieldnames + ["Qr String Data"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_csv_data)

            file_content = output.getvalue()
            file_name = "processed_invoices.csv"

            saved_file = save_file(file_name, file_content, "File", "Processed_Invoices", is_private=0)

            return Response(json.dumps({"file_url": saved_file.file_url}),
                            status=200, mimetype='application/json')

    return Response(json.dumps({"message": "Invoices created successfully."}),
                    status=200, mimetype='application/json')







@frappe.whitelist(allow_guest=True)
def create_invoices_using_csv():

    if frappe.request.method != "POST":
        return Response(
            json.dumps({"data": "Only POST requests are allowed."}),
            status=404, mimetype='application/json'
        )

    uploaded_file = frappe.request.files.get("file")
    image_files = frappe.request.files.getlist("images")
    qr_code_files = frappe.request.files.getlist("qr_codes")
    xml_files = frappe.request.files.getlist("xml_files")

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
            json.dumps({"data": "No invoice type selected in GPOS Settings."}),
            status=404, mimetype='application/json'
        )
    if post_to_pos_invoice and post_to_sales_invoice:
        return Response(
            json.dumps({"data": "Both invoice type are selected in GPOS Settings."}),
            status=404, mimetype='application/json'
        )

    file_content = uploaded_file.read().decode("utf-8")
    csv_data = list(csv.DictReader(StringIO(file_content)))
    image_map = {img.filename: img for img in image_files}
    qr_code_map = {qr.filename: qr for qr in qr_code_files}
    xml_map = {xml.filename: xml for xml in xml_files}


    invoices_data = defaultdict(lambda: {"items": [], "details": {}, "taxes": []})
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
                    row.get("Due Date (Payment Schedule)", datetime.today().strftime("%m-%d-%Y")),
                    "%m-%d-%Y"
                ).strftime("%Y-%m-%d"),
                "attachment": row.get("Attachments"),
                "custom_unique_id": row.get("unique_id"),
                "custom_zatca_pos_name": row.get("zatca_pos_name"),
                "custom_qr_code" : row.get("QR Code Filename"),
                "custom_xml" : row.get("XML Filename")
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
                "rate":float(row.get("Tax Rate")),
                # "amount":float(row.get("Tax Amount"))
            }
            invoices_data[invoice_id]["taxes"].append(tax)
            # return invoices_data[invoice_id]["taxes"]
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

        existing_invoice = frappe.db.exists({"doctype": "Sales Invoice", "custom_unique_id": details["custom_unique_id"]})
        if existing_invoice:
            return Response(
                json.dumps({"data": f"Invoice with unique_id '{details['custom_unique_id']}' already exists."}),
                status=404, mimetype='application/json'
            )

        invoice_type = "POS Invoice" if post_to_pos_invoice else "Sales Invoice"
        # total_tax_amount = sum(tax["amount"] for tax in data["taxes"])
        # total_item_amount = sum(item["amount"] for item in data["items"])
        # grand_total = total_item_amount + total_tax_amount

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
            # "total": grand_total
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


        qr_code_filename = details.get("custom_qr_code")
        if qr_code_filename and qr_code_filename in qr_code_map:
            qr_code_content = qr_code_map[qr_code_filename].read()
            file_path = frappe.utils.get_files_path(qr_code_filename, is_private=False)
            with open(file_path, "wb") as f:
                f.write(qr_code_content)
            file_url = f"/files/{qr_code_filename}"
            new_invoice.db_set("custom_qr_code", file_url)


        custom_xml_filename = details.get("custom_xml")
        if custom_xml_filename and custom_xml_filename in qr_code_map:
            custom_xml_content = qr_code_map[custom_xml_filename].read()

            file_path = frappe.utils.get_files_path(custom_xml_filename, is_private=False)
            with open(file_path, "wb") as f:
                f.write(custom_xml_content)

            file_url = f"/files/{custom_xml_filename}"

            new_invoice.db_set("custom_xml", file_url)


    return {
        "message": f"{len(invoices_created)} {invoice_type}s created successfully.",
        "invoices": invoices_created
    }

@frappe.whitelist(allow_guest=True)
def create_invoices_using_csv1():
    if frappe.request.method != "POST":
        return Response(
            json.dumps({"data": "Only POST requests are allowed."}),
            status=404, mimetype='application/json'
        )

    uploaded_file = frappe.request.files.get("file")
    if not uploaded_file or not uploaded_file.filename.endswith('.csv'):
        return Response(
            json.dumps({"data": "Valid CSV file is required."}),
            status=404, mimetype='application/json'
        )

    file_content = uploaded_file.read().decode("utf-8")
    csv_data = list(csv.DictReader(StringIO(file_content)))

    invoices_data = defaultdict(lambda: {"items": [], "details": {}, "taxes": []})
    invoices_created = []

    for row in csv_data:
        invoice_id = row.get("ID")
        if invoice_id:
            invoices_data[invoice_id]["details"] = {
                "customer": row.get("Customer"),
                "company": row.get("Company"),
                "posting_date": row.get("Date"),
                "currency": row.get("Currency", "USD"),
                "exchange_rate": row.get("Exchange Rate", "1"),
                "due_date": datetime.strptime(
                    row.get("Due Date (Payment Schedule)", datetime.today().strftime("%m/%d/%Y")),
                    "%m/%d/%Y"
                ).strftime("%Y-%m-%d"),
                "custom_unique_id": row.get("unique_id"),
                "custom_zatca_pos_name": row.get("zatca_pos_name"),
            }
            item = {
                "item_code": row.get("Item Name (Items)"),
                "qty": float(row.get("UOM Conversion Factor (Items)", "1")),
                "rate": float(row.get("Rate (Items)", "0")),
                "uom": row.get("UOM (Items)", "Nos"),
                "amount": float(row.get("Amount (Items)", "0")),
            }
            invoices_data[invoice_id]["items"].append(item)

    for invoice_id, data in invoices_data.items():
        details = data["details"]

        existing_invoice = frappe.db.exists({"doctype": "Sales Invoice", "custom_unique_id": details["custom_unique_id"]})
        if existing_invoice:
            return Response(
                json.dumps({"data": f"Invoice with unique_id '{details['custom_unique_id']}' already exists."}),
                status=404, mimetype='application/json'
            )

        invoice_type = "Sales Invoice"
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
        }

        new_invoice = frappe.get_doc(invoice_doc)
        new_invoice.insert(ignore_permissions=True)
        new_invoice.submit()
        invoices_created.append((invoice_id, new_invoice.name))

    # Update CSV with generated invoice names
    for row in csv_data:
        invoice_id = row.get("ID")
        if invoice_id:
            matched_invoice = next((inv[1] for inv in invoices_created if inv[0] == invoice_id), None)
            if matched_invoice:
                row["Invoice Name"] = matched_invoice

    # Save updated CSV
    updated_csv_path = "/mnt/data/updated_invoices.csv"
    with open(updated_csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
        fieldnames = csv_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    return {
        "message": f"{len(invoices_created)} invoices created successfully.",
        "invoices": [inv[1] for inv in invoices_created],
        "updated_csv": updated_csv_path
    }




