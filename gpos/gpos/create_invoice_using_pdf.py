import frappe
import re
import json
import pdfplumber
from pdf2image import convert_from_path
from pdf2image import convert_from_bytes
import pytesseract
from io import BytesIO
import fitz
from frappe.utils.file_manager import save_file
# Initialize Frappe
# frappe.init(site="zatca-live.erpgulf.com")
# frappe.connect()
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

@frappe.whitelist()
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

        invoice_data = extract_invoice_details_from_text(extracted_text, pdf_mapping)

        save_json(invoice_data)

        return {"invoice_data": invoice_data}

    except Exception as e:
        frappe.log_error(f"Error processing PDF: {str(e)}")
        return {"error": "Internal Server Error", "details": str(e)}


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



def extract_invoice_details_from_text(extracted_text, pdf_mapping):
    invoice_details = {}

    for key, pattern in pdf_mapping.items():
        if isinstance(pattern, dict):
            invoice_details[key] = {}

            for sub_key, sub_pattern in pattern.items():
                if isinstance(sub_pattern, (str, list)):
                    invoice_details[key][sub_key] = find_match(sub_pattern, extracted_text)

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
        return []

    line_pattern = line_item_config.get("pattern", "")
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
    create_invoices_from_json()


@frappe.whitelist(allow_guest=True)
def create_invoices_from_json():
    if not hasattr(frappe.local, "flags"):
        frappe.local.flags = frappe._dict()

    # pdf_bytes = uploaded_file.read()

    # invoice_id = frappe.form_dict.get("invoice_id")
    # zimra_submit = frappe.form_dict.get("zimra_submit", False)
    json_path = "/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/result.json"

    try:
        with open(json_path, "r") as f:
            invoice_data = json.load(f)
    except FileNotFoundError:
        return {"error": "Invoice JSON file not found."}, 404

    if not hasattr(frappe.local, "flags"):
        frappe.local.flags = frappe._dict()

    invoices_created = []
    customer_data = invoice_data.get("customer", {})

    customer_name = customer_data.get("name", "Unknown Customer").strip()
    customer_address = customer_data.get("address", "").replace("\n", " ").strip()

    if not frappe.db.exists("Customer", customer_name):
        new_customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Company",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
            "customer_primary_contact": customer_data.get("email", ""),
            "tax_id": customer_data.get("TIN", ""),
            "vat_number": customer_data.get("VAT", ""),
            "phone": customer_data.get("phone", ""),
            "address": customer_address,
            "city": customer_data.get("city", "Not Found"),
            "country": customer_data.get("country", "Not Found")
        })
        new_customer.insert(ignore_permissions=True, ignore_links=True)
        frappe.db.commit()

    supplier_data = invoice_data.get("supplier", {})
    supplier_name = supplier_data.get("name", "Unknown Supplier").strip()

    if not frappe.db.exists("Company", supplier_name):
        new_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": supplier_name,
            "default_currency": "USD",
            "tax_id": supplier_data.get("TIN", ""),
            "vat_number": supplier_data.get("VAT", ""),
            "email": supplier_data.get("email", ""),
            "phone": supplier_data.get("phone", ""),
            "address": supplier_data.get("address", "Not Found"),
            "city": supplier_data.get("city", "Not Found"),
            "country": supplier_data.get("country", "Not Found")
        })
        new_company.insert(ignore_permissions=True, ignore_links=True)
        frappe.db.commit()

    def safe_float(value, default=0.0):
        try:
            return float(re.sub(r"[^\d.]", "", str(value))) if value else default
        except ValueError:
            return default

    invoice_total = safe_float(invoice_data.get("invoice_total", "0"))
    vat_total = safe_float(invoice_data.get("vat_total", "0"))
    subtotal = safe_float(invoice_data.get("sub_total", "0"))

    if invoice_total == 0 and subtotal > 0:
        invoice_total = subtotal + vat_total

    # if invoice_total <= 0:
    #     return {"error": "Grand Total (Company Currency) must be greater than 0"}

    if not frappe.db.exists("Currency Exchange", {"from_currency": "SAR", "to_currency": "USD"}):
        return {"error": "Missing exchange rate for SAR to USD. Please add it manually"}

    invoice_doc = {
        "doctype": "Sales Invoice",
        "customer": customer_name,
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.add_days(frappe.utils.today(), 7),
        "company": supplier_name,
        "currency": "USD",
        "exchange_rate": 1.0,
        "items": [],
        "taxes": [],
        "grand_total": invoice_total,
        "base_grand_total": invoice_total
    }

    line_items = invoice_data.get("line_items", [])
    if not line_items:
        return {"error": "No line items found in invoice data"}

    for item in line_items:
        item_code = item.get("Code", "Unknown Item")
        item_name = item.get("Description", "No Description")

        if not frappe.db.exists("Item", item_code):
            new_item = frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name,
                "item_group": "All Item Groups",
                "custom_company":supplier_name,
                "stock_uom": "Nos",
                "is_sales_item": 1,
                "standard_rate": safe_float(item.get("Unit Price", "0")),
                "taxes": [{"item_tax_template": "Zimbabwe Tax - HT"}],
            })
            new_item.insert(ignore_permissions=True, ignore_links=True)
            frappe.db.commit()

        Unit_Price = safe_float(item.get("Unit Price", "0"))
        VAT_Amount = safe_float(item.get("VAT Amount", "0"))
        rate = max(Unit_Price - VAT_Amount, 0)

        invoice_doc["items"].append({
            "item_code": item_code,
            "item_name": item_name,
            "qty": safe_float(item.get("Quantity", "0")),
            "rate": rate,
            "item_tax_template": "Zimbabwe Tax - HT",
        })

    tax_rate = round((vat_total * 100 / subtotal), 2) if subtotal else 0

    invoice_doc["taxes"].append({
        "charge_type": "On Net Total",
        "account_head": "Freight and Forwarding Charges - HT(L",
        "description": "this is",
        "rate": tax_rate,
    })

    new_invoice = frappe.get_doc(invoice_doc)
    new_invoice.insert(ignore_permissions=True, ignore_links=True)
    new_invoice.save()

    invoices_created.append(new_invoice.name)

    return json.dumps({"message": f"{len(invoices_created)} invoice(s) created.", "invoices": invoices_created})




def write_qr_code_to_pdf(pdf_bytes, qr_code_string, zimra_response):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    new_page = doc.new_page(width=595, height=842)

    new_page.insert_text((50, 100), "QR Code Data:", fontsize=12, color=(0, 0, 0))
    new_page.insert_text((50, 120), qr_code_string, fontsize=10, color=(0, 0, 0))

    response_lines = zimra_response.split()
    formatted_lines = "\n".join([" ".join(response_lines[i:i+10]) for i in range(0, len(response_lines), 10)])

    new_page.insert_text((50, 160), "ZIMRA Response:", fontsize=12, color=(0, 0, 0))
    new_page.insert_textbox((50, 180, 500, 400), formatted_lines, fontsize=10, color=(0, 0, 0))

    output_pdf_path = "/tmp/Updated_Invoice.pdf"
    doc.save(output_pdf_path)
    doc.close()

    return output_pdf_path