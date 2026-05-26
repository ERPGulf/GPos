import cv2
import frappe
from frappe import _
from frappe.utils.data import add_to_date, get_time, getdate
from erpnext import get_region
from pyqrcode import create as qr_create
import base64
from base64 import b64encode
import io
import os

def create_qr_code(doc, method):
    """Create QR Code after saving Employee"""

    # Check field exists
    if not hasattr(doc, "custom_qr_code"):
        return

    fields = frappe.get_meta("Employee").fields

    auth_client_name = frappe.db.get_value("OAuth Client", {}, "name")

    if not auth_client_name:
        frappe.throw(_("No OAuth Client found"))

    auth_client = frappe.get_doc("OAuth Client", auth_client_name)

    app_name = auth_client.app_name

    if not app_name:
        frappe.throw(_("App name missing in OAuth Client"))

    settings = frappe.get_single("Claudion POS setting")

    machine_name = settings.zatca_multiple_setting or ""
    prefix = settings.prefix or ""

    app_key = base64.b64encode(app_name.encode()).decode("utf-8")

    for field in fields:

        if (
            field.fieldname == "custom_qr_code"
            and field.fieldtype == "Attach Image"
        ):

            # Mandatory validations
            if not doc.user_id:
                frappe.throw(
                    _("User ID missing for {}").format(doc.name)
                )

            if not frappe.local.conf.host_name:
                frappe.throw(
                    _("API URL (host_name) is missing in site config")
                )

            if not app_key:
                frappe.throw(
                    _("App key could not be generated")
                )

            # QR Content
            cleaned = (
                f"API_KEY: {doc.user_id} "
                f"Host: {frappe.local.conf.host_name} "
                f"APP_KEY: {app_key} "
                f"CLIENT_SECRET: {auth_client.get_password('client_secret') or ''} "
                f"MACHINE_NAME: {machine_name} "
                f"INVOICE_PREFIX: {prefix} "
                f"BRANCH_ID: {doc.custom_pos_profile or ''}"
            )

            # Encode QR Data
            base64_string = b64encode(cleaned.encode()).decode()

            # Generate QR
            qr_image = io.BytesIO()

            qr = qr_create(base64_string, error="L")

            qr.png(
                qr_image,
                scale=2,
                quiet_zone=1
            )

            filename = f"QR-CODE-{doc.name}.png".replace(
                os.path.sep,
                "__"
            )

            # Delete old file if exists
            old_file = frappe.db.get_value(
                "File",
                {
                    "attached_to_doctype": doc.doctype,
                    "attached_to_name": doc.name,
                    "file_name": filename
                },
                "name"
            )

            if old_file:
                frappe.delete_doc("File", old_file, force=True)

            # Save file
            _file = frappe.get_doc({
                "doctype": "File",
                "file_name": filename,
                "content": qr_image.getvalue(),
                "attached_to_doctype": doc.doctype,
                "attached_to_name": doc.name,
                "is_private": 0
            })

            _file.save(ignore_permissions=True)

            # Update Employee
            doc.db_set(
                "custom_qr_code",
                _file.file_url
            )

            break


def delete_qr_code_file(doc, method):
	"""Delete QR Code on deleted sales invoice"""


	if hasattr(doc, 'custom_qr_code'):
		if doc.get('custom_qr_code'):
			file_doc = frappe.get_list('File', {
				'file_url': doc.custom_qr_code,
				'attached_to_doctype': doc.doctype,
				'attached_to_name': doc.name
			})
			if len(file_doc):
				frappe.delete_doc('File', file_doc[0].name)
