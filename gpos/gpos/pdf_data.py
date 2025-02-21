import pdfplumber
import re
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBoxHorizontal, LTTextLineHorizontal
import json
def extract_text_and_tables(pdf_path):
    texts = []
    tables = []
    to_address_lines = []
    from_address_lines = []
    extracting_to = False
    extracting_from = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text)
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)

    for page_layout in extract_pages(pdf_path):
        for element in page_layout:
            if isinstance(element, (LTTextBoxHorizontal, LTTextLineHorizontal)):
                text = element.get_text().strip()

                # Identify the start of "To" section
                if text.upper() == "TO":
                    extracting_to = True
                    extracting_from = False
                    continue

                # Identify the start of "From" section
                if text.upper() == "FROM":
                    extracting_from = True
                    extracting_to = False
                    continue

                # Stop collecting lines when encountering an unrelated line
                if extracting_to and text.upper() == "FROM":
                    extracting_to = False
                    extracting_from = True
                    continue

                # Stop collecting lines when encountering an unrelated line
                if extracting_from and text.upper().startswith("PRICE QTY."):
                    extracting_from = False
                    continue

                # Collect lines for "To" section
                if extracting_to and not extracting_from:
                    to_address_lines.append(text)

                # Collect lines for "From" section
                if extracting_from:
                    from_address_lines.append(text)

    to_address = "\n".join(to_address_lines).strip()
    from_address = "\n".join(from_address_lines).strip()

    return texts, tables, to_address, from_address


def parse_header(text):
    header = {
        'date': '',
        'invoice_number': '',
    }

    # Extract date and invoice number
    date_invoice_match = re.search(r'Date Invoice #\s*\n(\d{2}-\d{2}-\d{4})\s+([^\n]+)', text)
    if date_invoice_match:
        header['date'] = date_invoice_match.group(1).strip()
        header['invoice_number'] = date_invoice_match.group(2).strip()

    return header


def parse_totals(text):
    totals = {
        "net_total": "",
        "vat_total": "",
        "total": ""
    }
    net_total_match = re.search(r'Net total:\s*([^\n]+)', text)
    if net_total_match:
        totals["net_total"] = net_total_match.group(1).strip()

    vat_total_match = re.search(r'VAT total:\s*([^\n]+)', text)
    if vat_total_match:
        totals["vat_total"] = vat_total_match.group(1).strip()

    total_match = re.search(r'Total:\s*([^\n]+)', text)
    if total_match:
        totals["total"] = total_match.group(1).strip()

    return totals


def parse_payment_details(text):
    payment_details = {
        "bank_name": "",
        "sort_code": "",
        "account_number": "",
        "payment_reference": ""
    }
    payment_match = re.search(r'PAYMENT DETAILS\n([\s\S]+?)\nNotes', text)
    if payment_match:
        payment_text = payment_match.group(1)
        bank_name_match = re.search(r'(Banks of Banks)', payment_text)
        if bank_name_match:
            payment_details["bank_name"] = bank_name_match.group(1).strip()

        sort_code_match = re.search(r'Bank/Sort Code:\s*([0-9]+)', payment_text)
        if sort_code_match:
            payment_details["sort_code"] = sort_code_match.group(1).strip()

        account_number_match = re.search(r'Account Number:\s*([0-9]+)', payment_text)
        if account_number_match:
            payment_details["account_number"] = account_number_match.group(1).strip()

        payment_ref_match = re.search(r'Payment Reference:\s*([A-Z0-9\-]+)', payment_text)
        if payment_ref_match:
            payment_details["payment_reference"] = payment_ref_match.group(1).strip()

    return payment_details


def parse_notes(text):
    notes_match = re.search(r'Notes\n([\s\S]+?)\nCloudion \|', text)
    return notes_match.group(1).strip() if notes_match else ""


def parse_contact(text):
    contact = {
        "email": "",
        "phone": ""
    }
    contact_match = re.search(r'Cloudion \| ([^\|]+) \| ([^\n]+)', text)
    if contact_match:
        contact["email"] = contact_match.group(1).strip()
        contact["phone"] = contact_match.group(2).strip()

    return contact


def parse_line_items(tables):
    line_items = []
    for table in tables:
        for row in table[3:]:  # Skip header row
            if len(row) >= 7:
                line_item = {
                    "Product": row[1].strip() if row[1] else "",
                    "Price": re.sub(r'[^\d\.\,]', '', row[2].split("\n")[-1].strip()) if row[2] else "",
                    "Qty.": row[3].strip() if row[3] else "",
                    "VAT": row[4].strip() if row[4] else "",
                    "Subtotal": re.sub(r'[^\d\.\,]', '', row[5].split("\n")[-1].strip()) if row[5] else "",
                    "subtotal_with_vat": re.sub(r'[^\d\.\,]', '', row[6].split("\n")[-1].strip()) if row[6] else ""
                }
                line_items.append(line_item)
    return line_items


def format_extracted_data(texts, tables, to_address, from_address):
    combined_text = "\n".join(texts)

    header = parse_header(combined_text)
    totals = parse_totals(combined_text)
    payment_details = parse_payment_details(combined_text)
    notes = parse_notes(combined_text)
    contact = parse_contact(combined_text)
    line_items = parse_line_items(tables)

    data = {
        "invoice": {
            "header": header,
            "from_address": from_address,
            "to_address": to_address,
            "line_items": line_items,
            "totals": totals,
            "payment_details": payment_details,
            "notes": notes,
            "contact": contact
        }
    }

    return data


def main(pdf_path):
    texts, tables, to_address, from_address = extract_text_and_tables(pdf_path)
    formatted_data = format_extracted_data(texts, tables, to_address, from_address)

    output_file = '/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/result.json'
    with open(output_file, 'w') as f:
        json.dump(formatted_data, f, indent=4)

pdf_path = '/opt/zatca-live/frappe-bench/apps/gpos/gpos/gpos/ACC-SINV-2025-00180 (1).pdf'
main(pdf_path)