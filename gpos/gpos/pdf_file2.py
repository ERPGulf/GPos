import frappe
import re
import json
import pdfplumber
from pdf2image import convert_from_path
from pdf2image import convert_from_bytes
import pytesseract
from io import BytesIO
# Initialize Frappe
# frappe.init(site="zatca-live.erpgulf.com")
# frappe.connect()
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

@frappe.whitelist(allow_guest=True)
def pdf_to_json():
    try:
        uploaded_file = frappe.request.files.get("file")
        company_name = frappe.form_dict.get("company_name")

        if not uploaded_file:
            return {"error": "Missing required parameter: 'file'"}
        if not company_name:
            return {"error": "Missing required parameter: 'company_name'"}

        pdf_bytes = uploaded_file.read()
        extracted_text = extract_text_from_pdf_bytes(pdf_bytes)

        if not extracted_text.strip():
            return {"error": "Failed to extract text from the provided PDF."}

        pdf_mapping = get_company_pdf_mapping(company_name)

        if not pdf_mapping:
            return {"error": f"No PDF Mapping JSON found for company: {company_name}"}

        invoice_data = extract_invoice_details_from_text(extracted_text, pdf_mapping, company_name)

        save_json(invoice_data)

        return {"invoice_data": invoice_data}

    except Exception as e:
        frappe.log_error(f"Error processing PDF: {str(e)}")
        return {"error": "Internal Server Error", "details": str(e)}


def get_company_pdf_mapping(company_name):
    file_doc = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Company", "attached_to_name": company_name.strip()},
        fields=["file_url"]
    )

    if not file_doc:
        frappe.msgprint(f"No PDF Mapping JSON found in Company attachments for {company_name}.")
        return None

    json_file_url = file_doc[0]["file_url"]
    json_file_path = frappe.get_site_path(json_file_url.strip("/"))

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            pdf_mapping = json.load(f)
        return pdf_mapping
    except Exception as e:
        frappe.msgprint(f"Error Loading JSON Template: {e}")
        return None


def extract_text_from_pdf_bytes(pdf_bytes):
    extracted_text = ""
    pdf_file = BytesIO(pdf_bytes)

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"

        if extracted_text.strip():
            return extracted_text
    except Exception as e:
        frappe.msgprint(f"Error using pdfplumber: {e}")

    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
        for image in images:
            extracted_text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        frappe.msgprint(f"OCR extraction failed: {e}")

    return extracted_text


def extract_address_details(text, start_keyword, end_keywords):
    pattern = rf"{start_keyword}([\s\S]*?)(?={'|'.join(end_keywords)})"
    match = re.search(pattern, text, re.MULTILINE)

    if match:
        full_address = match.group(1).strip().split("\n")
        full_address = [
            line.strip() for line in full_address 
            if line.strip() and not re.search(r"Page\s*\d+|Date\s*\d{2}/\d{2}/\d{4}", line, re.IGNORECASE)
        ]

        city = full_address[-2] if len(full_address) >= 2 else "Not Found"
        country = full_address[-1] if len(full_address) >= 1 else "Not Found"

        clean_address = " ".join(full_address)

        return clean_address, city, country

    return "Not Found", "Not Found", "Not Found"


def extract_invoice_details_from_text(extracted_text, pdf_mapping,company_name):
    invoice_details = {}

    for key, pattern in pdf_mapping.items():
        if isinstance(pattern, dict):
            invoice_details[key] = {}
            for sub_key, sub_pattern in pattern.items():
                if isinstance(sub_pattern, str) or isinstance(sub_pattern, list):
                    invoice_details[key][sub_key] = find_match(sub_pattern, extracted_text)

            if key == "supplier":
                supplier_address, supplier_city, supplier_country = extract_address_details(
                    extracted_text, company_name, ["TIN NO"]
                )
                invoice_details[key]["address"] = supplier_address
                invoice_details[key]["city"] = supplier_city
                invoice_details[key]["country"] = supplier_country

            if key == "customer":
                customer_address, customer_city, customer_country = extract_address_details(
                    extracted_text, "Customer Address:", ["Customer Email", "Customer Tel No"]
                )
                invoice_details[key]["address"] = customer_address
                invoice_details[key]["city"] = customer_city
                invoice_details[key]["country"] = customer_country
        
        elif isinstance(pattern, list):
            invoice_details[key] = find_match(pattern, extracted_text)
        
        elif isinstance(pattern, str):
            invoice_details[key] = find_match(pattern, extracted_text)

    invoice_details["line_items"] = extract_line_items(extracted_text, pdf_mapping)
    return invoice_details


def find_match(patterns, text):
    if isinstance(patterns, str):
        patterns = [patterns]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip() if match.lastindex else match.group(0).strip()
    
    return "Not Found"


def extract_line_items(extracted_text, pdf_mapping):
    line_items = []
    line_item_config = pdf_mapping.get("line_items", {})

    if not isinstance(line_item_config, dict):
        frappe.msgprint("Error: 'line_items' format in template is incorrect. Expected a dictionary.")
        return []

    line_pattern = line_item_config.get("pattern", "")

    if not line_pattern:
        frappe.msgprint(" No line items pattern found in the template.")
        return []

    matches = re.findall(line_pattern, extracted_text, re.MULTILINE)

    def safe_float(value):
        value = re.sub(r"[^\d.]", "", value.replace(",", ""))
        return float(value) if value else 0.0

    fields = line_item_config.get("fields", [])

    for match in matches:
        item = {}
        for i, field in enumerate(fields):
            if i < len(match):
                item[field] = safe_float(match[i]) if "Price" in field or "Quantity" in field else match[i].strip()
        line_items.append(item)

    return line_items


def save_json(invoice_data):
    output_json_path = "/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/result.json"
    try:
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(invoice_data, f, indent=4)
        frappe.msgprint(f"\n Invoice data saved to {output_json_path}")
    except Exception as e:
        frappe.msgprint(f"Error saving JSON: {e}")





# def convert_pdf_to_images(pdf_path):
#     images = convert_from_path(pdf_path, dpi=300)
#     return images

# def extract_text_from_images(images):
#     extracted_text = ""
#     for image in images:
#         extracted_text += pytesseract.image_to_string(image) + "\n"
#     return extracted_text

# def extract_invoice_details_from_text(extracted_text):
#     invoice_details = {
#         "invoice_number": "",
#         "invoice_date": "",
#         "supplier": "",
#         "supplier_address":"",
#         "customer": "",
#         "customer_address": "",
#         "supplier_tin": "",
#         "customer_tin": "",
#         "supplier_vat": "",
#         "customer_vat": "",
#         "email": "",
#         "phone": "",
#          "account_details": {
#             "Account": "",
#             "Tax Exempt": "",
#             "Tax Reference": "",
#             "Sales Code": ""
#         },
#         "line_items": [],
#         "subtotal": "",
#         "vat_total": "",
#         "total": ""
#     }

#     def find_match(pattern):
#         match = re.search(pattern, extracted_text, re.IGNORECASE)
#         return match.group(1).strip() if match else ""
#     def clean_address(address):
#         return " ".join(address.splitlines()).strip()

#     invoice_details["invoice_number"] = find_match(r'Document No\s*\n*(\S+)')
#     invoice_details["invoice_date"] = find_match(r'(\d{2}/\d{2}/\d{4})')
#     invoice_details["supplier"] = find_match(r'([A-Z\s]+ TRADING)')
#     raw_supplier_address = find_match(r'(?<=LIMITED\n)([A-Z0-9\s\n,-]+)')
#     invoice_details["supplier_address"] = clean_address(raw_supplier_address)

#     customer_match = re.search(r'Customer Name:\s*([^\n]+)', extracted_text, re.IGNORECASE)
#     if customer_match:
#         customer_name = customer_match.group(1).strip()
#         customer_name = re.split(r'\b(Deliver to|Ship to|Bill to)\b', customer_name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
#         invoice_details["customer"] = customer_name
#     raw_customer_address = find_match(r'Customer Address:\s*([\s\S]+?)\nCustomer Email')
#     invoice_details["customer_address"] = clean_address(raw_customer_address)
#     invoice_details["supplier_tin"] = find_match(r'TIN NO\s*:\s*(\d+)')
#     invoice_details["supplier_vat"] = find_match(r'VAT NO\s*:\s*(\d+)')
#     invoice_details["customer_tin"] = find_match(r'Customer\s+TIN NO\s*:\s*(\d+)')
#     invoice_details["customer_vat"] = find_match(r'Customer\s+VAT NO\s*:\s*(\d+)')
#     invoice_details["email"] = find_match(r'Email\s*:\s*([\w\.-]+@[\w\.-]+)')
#     invoice_details["phone"] = find_match(r'Tel\s*:\s*([\d-]+)')

#     invoice_details["subtotal"] = find_match(r'Sub Total Excl.\s*USD(\d+\.\d+)')
#     invoice_details["vat_total"] = find_match(r'VAT Total\s*USD(\d+\.\d+)')
#     invoice_details["total"] = find_match(r'Invoice Total\s*USD(\d+\.\d+)')

#     lines = extracted_text.split("\n")
#     found_account_headers = False
#     account_headers = []
#     found_headers = False
#     headers = []
#     line_items = []

#     for index, line in enumerate(lines):
#         line = line.strip()

#         if "Account Tax Exempt Tax Reference Sales Code" in line:
#             account_headers = re.split(r'\s{2,}', line)
#             found_account_headers = True
#             continue

#         if found_account_headers and line:
#             account_values = re.split(r'\s{2,}', line)

#             while len(account_values) < len(account_headers):
#                 account_values.append("")

#             invoice_details["account_details"] = {
#                 "Account": account_values[0][:-1].strip() if account_values[0].strip().endswith("N") else account_values[0].strip() if len(account_values) > 0 else "",
#                 "Tax Exempt": account_values[1] if len(account_values) > 1 else "N",
#                 "Tax Reference": account_values[2] if len(account_values) > 2 else "",
#                 "Sales Code": account_values[3] if len(account_values) > 3 else ""
#             }

#             found_account_headers = False




#         if "Code Description Quantity Unit Price (Incl.) VAT Amount Nett Price (Incl.)" in line:
#             found_headers = True
#             headers = ["Code", "Description", "Quantity", "Unit Price (Incl.)", "VAT Amount", "Nett Price (Incl.)"]
#             continue

#         if found_headers:
#             values = line.split()
#             if len(values) >= 6 and values[0].replace("/", "").isdigit():
#                 line_items.append({
#                     "Code": values[0],
#                     "Description": " ".join(values[1:-4]),
#                     "Quantity": values[-4],
#                     "Unit Price (Incl.)": values[-3],
#                     "VAT Amount": values[-2],
#                     "Nett Price (Incl.)": values[-1]
#                 })

#     invoice_details["line_items"] = line_items

#     return invoice_details

# def save_invoice_data(pdf_path, output_json_path):
#     images = convert_pdf_to_images(pdf_path)
#     extracted_text = extract_text_from_images(images)
#     invoice_data = extract_invoice_details_from_text(extracted_text)

#     with open(output_json_path, "w") as f:
#         json.dump(invoice_data, f, indent=4)



# pdf_path = '/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/CHANGA TAX INVOICE USD (3).pdf'
# output_json_path = '/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/result.json'

# save_invoice_data(pdf_path, output_json_path)












# @frappe.whitelist(allow_guest=True)
# def create_invoices_from_json():
#     if not hasattr(frappe.local, "flags"):
#         frappe.local.flags = frappe._dict()

#     json_path = "/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/result.json"

#     try:
#         with open(json_path, "r") as f:
#             invoice_data = json.load(f)
#     except FileNotFoundError:
#         return {"error": "Invoice JSON file not found."}, 404

#     invoices_created = []
#     customer_name = invoice_data.get("customer")

#     if not frappe.db.exists("Customer", customer_name):
#         new_customer = frappe.get_doc({
#             "doctype": "Customer",
#             "customer_name": customer_name,
#             "customer_type": "Company",
#             "customer_group": "All Customer Groups",
#             "territory": "All Territories",
#             "customer_primary_contact": invoice_data.get("email", ""),
#             "tax_id": invoice_data.get("customer_tin", ""),
#         })
#         new_customer.insert(ignore_permissions=True, ignore_links=True)
#         frappe.db.commit()
#         frappe.msgprint(f"New Customer '{customer_name}' created.", alert=True)



#     supplier_name = invoice_data.get("supplier")

#     if not frappe.db.exists("Company", supplier_name):
#         new_company = frappe.get_doc({
#             "doctype": "Company",
#             "company_name": supplier_name,
#             "default_currency": "USD",
#         })
#         new_company.insert(ignore_permissions=True, ignore_links=True)
#         frappe.db.commit()
#         frappe.msgprint(f"New Company '{supplier_name}' created.", alert=True)



#     invoice_doc = {
#         "doctype": "Sales Invoice",
#         "customer": customer_name,
#         "posting_date": frappe.utils.today(),
#         "due_date": frappe.utils.add_days(frappe.utils.today(), 7),
#         "company": supplier_name,
#         "currency": "USD",
#         "exchange_rate": 1.0,
#         "items": [],
#         "taxes": [],
#         "total": invoice_data.get("total"),
#     }


#     for item in invoice_data.get("line_items", []):
#         item_code = item.get("Code", "")
#         item_name = item.get("Description", "")

#         if not frappe.db.exists("Item", item_code):
#             new_item = frappe.get_doc({
#                 "doctype": "Item",
#                 "item_code": item_code,
#                 "item_name": item_name,
#                 "item_group": "All Item Groups",
#                 "stock_uom": "Nos",
#                 "is_sales_item": 1,
#                 "standard_rate": float(item.get("Unit Price (Incl.)", "0") or "0"),
#                 "taxes": [{"item_tax_template": "Zimbabwe Tax - HT"}],
#             })
#             new_item.insert(ignore_permissions=True, ignore_links=True)
#             frappe.db.commit()

#         Unit_Price = float(item.get("Unit Price (Incl.)", "0").replace("USD", "").strip())
#         VAT_Amount = float(item.get("VAT Amount", "0").replace("USD", "").strip())
#         rate = Unit_Price - VAT_Amount

#         invoice_doc["items"].append({
#             "item_code": item_code,
#             "item_name": item_name,
#             "qty": float(item.get("Quantity")),
#             "rate": rate,
#             "item_tax_template": "Zimbabwe Tax - HT",
#         })
#     vat_total = float(invoice_data.get("vat_total"))
#     subtotal = float(invoice_data.get("subtotal"))
#     tax_rate = round((vat_total * 100 / subtotal), 2) if subtotal else 0

#     invoice_doc["taxes"].append({
#         "charge_type": "On Net Total",
#         "account_head": "Freight and Forwarding Charges - HT",
#         "description": "this is ",
#         "rate": tax_rate,
#     })



#     new_invoice = frappe.get_doc(invoice_doc)
#     new_invoice.insert(ignore_permissions=True, ignore_links=True)
#     new_invoice.save()

#     invoices_created.append(new_invoice.name)

#     return json.dumps({"message": f"{len(invoices_created)} invoice(s) created.", "invoices": invoices_created})