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
