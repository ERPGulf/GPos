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


@frappe.whitelist(allow_guest=True)
def generate_token_secure(api_key, api_secret, app_key):
    try:
        try:
            app_key = base64.b64decode(app_key).decode("utf-8")
        except Exception as e:
            return Response(
                json.dumps(
                    {"message": "Security Parameters are not valid", "user_count": 0}
                ),
                status=401,
                mimetype="application/json",
            )
        clientID, clientSecret, clientUser = frappe.db.get_value(
            "OAuth Client",
            {"app_name": app_key},
            ["client_id", "client_secret", "user"],
        )
        doc = frappe.db.get_value(
            "OAuth Client",
            {"app_name": app_key},
            ["name", "client_id", "client_secret", "user"],
        )

        if clientID is None:
            # return app_key
            return Response(
                json.dumps(
                    {"message": "Security Parameters are not valid", "user_count": 0}
                ),
                status=401,
                mimetype="application/json",
            )

        client_id = clientID  # Replace with your OAuth client ID
        client_secret = clientSecret  # Replace with your OAuth client secret

        url = (
            frappe.local.conf.host_name
            + "/api/method/frappe.integrations.oauth2.get_token"
        )

        payload = {
            "username": api_key,
            "password": api_secret,
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        files = []
        headers = {"Content-Type": "application/json"}

        response = requests.request("POST", url, data=payload, files=files)

        if response.status_code == 200:

            result_data = json.loads(response.text)

            return Response(
                json.dumps({"data": result_data}),
                status=200,
                mimetype="application/json",
            )

        else:

            frappe.local.response.http_status_code = 401
            return json.loads(response.text)

    except Exception as e:

        return Response(
            json.dumps({"message": e, "user_count": 0}),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def create_refresh_token(refresh_token):
    url = (
        frappe.local.conf.host_name + "/api/method/frappe.integrations.oauth2.get_token"
    )

    payload = f"grant_type=refresh_token&refresh_token={refresh_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    files = []
    response = requests.post(url, headers=headers, data=payload, files=files)

    if response.status_code == 200:
        try:
            message_json = json.loads(response.text)
            new_message = {
                "access_token": message_json["access_token"],
                "expires_in": message_json["expires_in"],
                "token_type": message_json["token_type"],
                "scope": message_json["scope"],
                "refresh_token": message_json["refresh_token"],
            }

            return Response(
                json.dumps({"data": new_message}),
                status=200,
                mimetype="application/json",
            )
        except json.JSONDecodeError as e:
            return Response(
                json.dumps({"data": f"Error decoding JSON: {e}"}),
                status=401,
                mimetype="application/json",
            )
    else:
        return Response(
            json.dumps({"data": response.text}), status=401, mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def get_items(item_group=None):
    fields = [
        "name",
        "stock_uom",
        "item_name",
        "item_group",
        "description",
    ]
    filters = {"item_group": ["like", f"%{item_group}%"]} if item_group else {}
    items = frappe.get_all("Item", fields=fields, filters=filters)


    grouped_items = {}

    for item in items:
        uoms = frappe.get_all(
            "UOM Conversion Detail",
            filters={"parent": item.name},
            fields=["uom", "conversion_factor"]
        )
        barcodes = frappe.get_all(
            "Item Barcode",
            filters={"parent": item.name},
            fields=["barcode", "uom"]
        )
        item_prices = frappe.get_all(
            "Item Price",
            fields=["price_list_rate", "uom"],
            filters={"item_code": item.name},  # fix item.item_code to item.name
        )

        # Build a mapping of UOM -> price
        price_map = {price.uom: price.price_list_rate for price in item_prices}

        if item.item_group not in grouped_items:
            grouped_items[item.item_group] = {
                "item_group_id": item.item_group,
                "item_group": item.item_group,
                "items": [],
            }

        grouped_items[item.item_group]["items"].append(
            {
                "item_id": item.name,
                "item_code": item.name,  # assuming 'name' is the item_code here
                "item_name": item.item_name,
                "tax_percentage": (
                    item.get('custom_tax_percentage') or 0.0
                ),
                "description": item.description,
                "barcodes": [
                    {"barcode": barcode.barcode, "uom": barcode.uom}
                    for barcode in barcodes
                ],
                "uom": [
                    {
                        "uom": uom.uom,
                        "conversion_factor": uom.conversion_factor,
                        "price": price_map.get(uom.uom, 0.0)  # fetch price for this uom
                    }
                    for uom in uoms
                ],
            }
        )

    result = list(grouped_items.values())
    return Response(
        json.dumps({"data": result}), status=200, mimetype="application/json"
    )


@frappe.whitelist()
def add_user_key(user_key, user_name):
    frappe.db.set_value("User", user_name, {"user_key": user_key})
    return f"user key:{user_key} added to user name: {user_name}"


@frappe.whitelist(allow_guest=True)
def user_login_details(user, log_in, log_out):
    doc = frappe.get_doc(
        {
            "doctype": "user login details",
            "user": user,
            "log_in": log_in,
            "log_out": log_out,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


from frappe.exceptions import DoesNotExistError


@frappe.whitelist(allow_guest=True)
def create_customer(
    customer_name, lead_name, email_id=None, gender=None, mobile_no=None
):
    try:
        lead = frappe.get_all(
            "Lead", fields=["lead_name"], filters={"name": ["like", f"{lead_name}"]}
        )
        # return customer
        if lead:
            # If customer exists, update the existing customer's fields
            existing_customer = frappe.get_all(
                "Customer",
                fields=["name"],
                filters={"lead_name": ["like", f"{lead_name}"]},
            )
            existing_customer = frappe.get_doc("Customer", existing_customer[0].name)

            existing_customer.customer_name = customer_name
            existing_customer.email_id = email_id
            existing_customer.gender = gender
            existing_customer.mobile_no = mobile_no
            # Update any other fields as needed
            existing_customer.save(ignore_permissions=True)
            frappe.db.commit()
            return Response(
                json.dumps({"data": "Customer updated successfully"}),
                status=200,
                mimetype="application/json",
            )
        else:
            # If customer doesn't exist, create a new customer
            doc = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "mobile_no": mobile_no,
                    "lead_name": lead_name,
                    "email_id": email_id,
                    "gender": gender,
                    # Add more fields as needed
                }
            )
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return Response(
                json.dumps({"data": "Customer created successfully"}),
                status=200,
                mimetype="application/json",
            )
    except DoesNotExistError:
        # Handle DoesNotExistError if needed
        pass


@frappe.whitelist(allow_guest=True)
def customer_list(id=None):
    doc = frappe.get_list(
        "Customer",
        fields=["name as id", "mobile_no as phone_no", "customer_name"],
        filters={"name": ["like", f"{id}"]} if id else None,
    )
    return Response(json.dumps({"data": doc}), status=200, mimetype="application/json")


@frappe.whitelist(allow_guest=True)
def cache1():
    doc = frappe.cache.set_value("key", "testing")
    return doc


@frappe.whitelist(allow_guest=True)
def cache2():
    doc = cache1()
    doc1 = frappe.cache.get_value("key")
    return doc1


@frappe.whitelist(allow_guest=True)
def pos_setting(machine_name):
    systemSettings = frappe.get_doc("pos setting")
    var = True if systemSettings.show_item == 1 else False
    Zatca_Multiple_Setting = (
        frappe.get_doc("Zatca Multiple Setting", machine_name) if machine_name else None
    )
    # return Zatca_Multiple_Setting
    linked_doctype = (
        Zatca_Multiple_Setting.custom_linked_doctype if Zatca_Multiple_Setting else None
    )

    zatca = (
        frappe.get_doc("Company", linked_doctype)
        if linked_doctype
        else frappe.get_doc("Company", "Zatca Live (Demo)")
    )
    address = frappe.get_all(
        "Address",
        fields=[
            "address_line1",
            "address_line2",
            "custom_building_number",
            "city",
            "pincode",
            "state",
            "country",
        ],
        filters=[
            ["is_your_company_address", "=", "1"],
            ["Dynamic Link", "link_name", "=", "Zatca Live"],
        ],
        limit=1,
    )

    if machine_name:
        certificate = Zatca_Multiple_Setting.custom_certficate
        private_key = Zatca_Multiple_Setting.custom_private_key
        public_key = Zatca_Multiple_Setting.custom_public_key
    else:
        certificate = zatca.custom_certificate
        private_key = zatca.custom_private_key
        public_key = zatca.custom_public_key

    encoded_certificate = base64.b64encode(certificate.encode("utf-8")).decode("utf-8")

    encoded_private_key = base64.b64encode(private_key.encode("utf-8")).decode("utf-8")
    encoded_public_key = base64.b64encode(public_key.encode("utf-8")).decode("utf-8")
    # return encoded_certificate,encoded_private_key,encoded_public_key

    address_record = address[0] if address else None

    data = {
        "discount_field": systemSettings.discount_field,
        "prefix_included_or_not": systemSettings.prefix_included_or_not,
        "no_of_prefix_character": int(systemSettings.no_of_prefix_character),
        "prefix": systemSettings.prefix,
        "item_code_total_digits": int(systemSettings.item_code_total_digits),
        "item_code_starting_position": int(systemSettings.item_code_starting_position),
        "weight_starting_position": int(systemSettings.weight_starting_position),
        "weight_total_digitsexcluding_decimal": int(
            systemSettings.weight_total_digitsexcluding_decimal
        ),
        "no_of_decimal_in_weights": int(systemSettings.no_of_decimal_in_weights),
        "price_included_in_barcode_or_not": int(
            systemSettings.price_included_in_barcode_or_not
        ),
        "price_starting_position": int(systemSettings.price_starting_position),
        "price_total_digitsexcluding_decimals": int(
            systemSettings.price_total_digitsexcluding_decimals
        ),
        "no_of_decimal_in_price": int(systemSettings.no_of_decimal_in_price),
        "show_item_pictures": var,
        "inclusive": systemSettings.inclusive,
        "exclusive": systemSettings.exclusive,
        "post_to_sales_invoice": systemSettings.post_to_sales_invoice,
        "post_to_pos_invoice": systemSettings.post_to_pos_invoice,
        "is_tax_included_in_price": systemSettings.is_tax_included_in_price,
        "tax_percentage": systemSettings.tax_percentage,
        "taxes": [
            {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "tax_rate": tax.rate,
                "total": tax.total,
                "description": tax.description,
            }
            for tax in systemSettings.sales_taxes_and_charges
        ],
        "zatca": {
            "company_name": zatca.name,
            "company_taxid": zatca.tax_id,
            "certificate": encoded_certificate,
            "pih": (
                Zatca_Multiple_Setting.custom_pih
                if Zatca_Multiple_Setting
                else zatca.custom_pih
            ),
            "Abbr": zatca.abbr,
            "tax_id": zatca.tax_id,
            "private_key": encoded_private_key,
            "public_key": encoded_public_key,
            "linked_doctype": (
                Zatca_Multiple_Setting.custom_linked_doctype
                if Zatca_Multiple_Setting
                else None
            ),
            "company_registration_no": zatca.custom_company_registration,
            "address": (
                {
                    "address_line1": (
                        address_record.address_line1 if address_record else None
                    ),
                    "city": address_record.city if address_record else None,
                    "pincode": (
                        int(address_record.pincode)
                        if address_record and address_record.pincode
                        else None
                    ),
                    "country": address_record.country if address_record else None,
                    "building_number": (
                        int(address_record.custom_building_number)
                        if address_record and address_record.custom_building_number
                        else None
                    ),
                }
                if address_record
                else None
            ),
        },
    }
    return Response(json.dumps({"data": data}), status=200, mimetype="application/json")


@frappe.whitelist(allow_guest=True)
def warehouse_details(id=None):
    # Define the filter
    filters = {"name": ["like", f"%{id}%"]} if id else {}

    pos_invoices = frappe.get_list("POS Invoice", fields=["name"], filters=filters)

    # Initialize list to store all items with warehouse details including POS Invoice name
    all_items_with_warehouse_details = []

    # Iterate over each POS Invoice
    for invoice in pos_invoices:
        # Fetch items for the current invoice
        items = frappe.get_all(
            "POS Invoice Item",
            fields=["item_code", "warehouse"],
            filters={"parent": invoice["name"]},
        )

        # Iterate over items of the current invoice
        for item in items:
            # Check if warehouse is not None before fetching details
            if item["warehouse"]:
                try:
                    # Fetch warehouse details
                    warehouse_details = frappe.get_doc("Warehouse", item["warehouse"])
                    # Create dictionary with item, warehouse, and POS Invoice details
                    item_with_details = {
                        "id": invoice["name"],
                        "item_code": item["item_code"],
                        "warehouse": item["warehouse"],
                        "mobile_no": getattr(warehouse_details, "mobile_no", None),
                        "address_line": getattr(
                            warehouse_details, "address_line_1", None
                        ),
                    }
                    # Append item details to the list
                    all_items_with_warehouse_details.append(item_with_details)
                except frappe.DoesNotExistError:
                    print(f"Warehouse {item['warehouse']} not found")
            else:
                print(f"Item {item['item_code']} does not have a warehouse assigned")

    return Response(
        json.dumps({"data": all_items_with_warehouse_details}),
        status=200,
        mimetype="application/json",
    )


@frappe.whitelist(allow_guest=True)
def wallet_refund_request(user, amount, transaction_id=None):
    wallet_refund = frappe.get_doc(
        {
            "doctype": "wallet refund",
            "user": user,
            "amount": amount,
            "transaction_id": transaction_id,
        }
    )

    wallet_refund.insert(ignore_permissions=True)
    wallet_refund.save()
    doc = frappe.get_all(
        "wallet refund",
        fields=["user", "amount", "transaction_id"],
        filters={"name": ["like", f"{wallet_refund.name}"]},
    )
    return Response(json.dumps({"data": doc}), status=200, mimetype="application/json")


@frappe.whitelist(allow_guest=False)
def generate_token_secure_for_users(username, password, app_key):

    # return Response(json.dumps({"message": "2222 Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')
    frappe.log_error(
        title="Login attempt",
        message=str(username) + "    " + str(password) + "    " + str(app_key + "  "),
    )
    try:
        try:
            app_key = base64.b64decode(app_key).decode("utf-8")
        except Exception as e:
            return Response(
                json.dumps(
                    {"message": "Security Parameters are not valid", "user_count": 0}
                ),
                status=401,
                mimetype="application/json",
            )
        clientID, clientSecret, clientUser = frappe.db.get_value(
            "OAuth Client",
            {"app_name": app_key},
            ["client_id", "client_secret", "user"],
        )

        if clientID is None:
            # return app_key
            return Response(
                json.dumps(
                    {"message": "Security Parameters are not valid", "user_count": 0}
                ),
                status=401,
                mimetype="application/json",
            )

        client_id = clientID  # Replace with your OAuth client ID
        client_secret = clientSecret  # Replace with your OAuth client secret
        url = (
            frappe.local.conf.host_name
            + "/api/method/frappe.integrations.oauth2.get_token"
        )
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            # "grant_type": "refresh_token"
        }
        files = []
        headers = {"Content-Type": "application/json"}
        response = requests.request("POST", url, data=payload, files=files)
        # var = frappe.get_list("Customer", fields=["name as id", "full_name","email", "mobile_no as phone",], filters={'name': ['like', username]})
        qid = frappe.get_list(
            "User",
            fields=["name as id", "Full Name", "mobile_no as phone", "email"],
            filters={"name": ["like", username]},
        )
        systemSettings = frappe.get_doc("pos setting")
        if response.status_code == 200:

            response_data = json.loads(response.text)

            result = {
                "token": response_data,
                "user": qid[0] if qid else {},
                "time": str(now_datetime()),
                "branch_id": systemSettings.branch,
            }
            return Response(
                json.dumps({"data": result}), status=200, mimetype="application/json"
            )
        else:

            frappe.local.response.http_status_code = 401
            return json.loads(response.text)

    except Exception as e:
        # frappe.local.response.http_status_code = 401
        # return json.loads(response.text)
        return Response(
            json.dumps({"message": e, "user_count": 0}),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def getOfflinePOSUsers(id=None, offset=0, limit=50):
    from frappe.utils.password import get_decrypted_password
    import base64

    mypass = get_decrypted_password(
        "POS Offline Users", "3ff95f9d07", "password", False
    )

    docs = frappe.db.get_all(
        "POS Offline Users",
        fields=[
            "name",
            "offine_username",
            "shop_name",
            "password",
            "user as actual_user_name,branch_address",
            "printe_template as print_template",
        ],
        # filters=filters,
        order_by="offine_username",
        limit_start=offset,
        limit_page_length=limit,
    )

    for doc in docs:
        doc.password = base64.b64encode(
            get_decrypted_password("POS Offline Users", doc.name, "password").encode(
                "utf-8"
            )
        ).decode("utf-8")
        # if not client_secret:
        #     continue

    return Response(json.dumps({"data": docs}), status=200, mimetype="application/json")


@frappe.whitelist(allow_guest=True)
def parse_json_field(field):
    try:
        return json.loads(field) if isinstance(field, str) else field
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format for field: {field}")


@frappe.whitelist(allow_guest=False)
def optimize_image_content(content, content_type):
    """Optimize image content if required."""
    args = {"content": content, "content_type": content_type}
    if frappe.form_dict.max_width:
        args["max_width"] = int(frappe.form_dict.max_width)
    if frappe.form_dict.max_height:
        args["max_height"] = int(frappe.form_dict.max_height)
    return optimize_image(**args)


@frappe.whitelist(allow_guest=False)
def attach_field_to_doc(doc):
    """Attach the file to a specific field in the document."""
    attach_field = frappe.get_doc(frappe.form_dict.doctype, frappe.form_dict.docname)
    setattr(attach_field, frappe.form_dict.fieldname, doc.file_url)
    attach_field.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=False)
def process_file_upload(file, ignore_permissions, is_private=False):
    """Handle the file upload process."""
    content = file.stream.read()
    filename = file.filename
    content_type = guess_type(filename)[0]

    if frappe.form_dict.optimize and content_type.startswith("image/"):
        content = optimize_image_content(content, content_type)

    frappe.local.uploaded_file = content
    frappe.local.uploaded_filename = filename

    doc = frappe.get_doc(
        {
            "doctype": "File",
            "attached_to_doctype": frappe.form_dict.doctype,
            "attached_to_name": frappe.form_dict.docname,
            "attached_to_field": frappe.form_dict.fieldname,
            "folder": frappe.form_dict.folder or "Home",
            "file_name": filename,
            "file_url": frappe.form_dict.fileurl,
            "is_private": cint(is_private),  # Use the is_private parameter
            "content": content,
        }
    ).save(ignore_permissions=ignore_permissions)

    if frappe.form_dict.fieldname:
        attach_field_to_doc(doc)

    return doc.file_url


@frappe.whitelist(allow_guest=False)
def upload_file():
    """To upload files into the Doctype"""
    _, ignore_permissions = validate_user_permissions()
    files = frappe.request.files
    file_names = []
    urls = []

    for key, file in files.items():
        file_names.append(key)
        urls.append(process_file_upload(file, ignore_permissions))
    return urls


@frappe.whitelist(allow_guest=False)
def validate_user_permissions():
    """Validate user permissions and return user and ignore_permissions."""
    if frappe.session.user == "Guest":
        if frappe.get_system_settings("allow_guests_to_upload_files"):
            return None, True
        raise frappe.PermissionError
    else:
        user = frappe.get_doc("User", frappe.session.user)
        return user, False


@frappe.whitelist(allow_guest=False)
def get_number_of_files(file_storage):
    """To get the number of total files"""
    if hasattr(file_storage, "get_num_files") and callable(file_storage.get_num_files):
        return file_storage.get_num_files()
    else:
        return 0

from frappe import ValidationError

@frappe.whitelist(allow_guest=False)
def create_invoice(
    customer_name,
    items,
    PIH,
    machine_name,
    Customer_Purchase_Order=None,
    payments=None,
    discount_amount=None,
    unique_id=None,

):
    try:

        pos_settings = frappe.get_doc("pos setting")

        items = parse_json_field(frappe.form_dict.get("items"))
        payments = parse_json_field(frappe.form_dict.get("payments"))
        discount_amount = float(frappe.form_dict.get("discount_amount", 0))
        Customer_Purchase_Order = frappe.form_dict.get("Customer_Purchase_Order")
        unique_id = frappe.form_dict.get("unique_id")
        PIH = frappe.form_dict.get("PIH")


        for item in items:
            item["rate"] = float(item.get("rate", 0))
            item["quantity"] = float(item.get("quantity", 0))

        for payment in payments or []:
            payment["amount"] = float(payment.get("amount", 0))

        customer_details = frappe.get_all(
            "Customer", fields=["name"], filters={"name": ["like", customer_name]}
        )
        if not customer_details:
            return Response(
                json.dumps({"data": "Customer name not found"}),
                status=404,
                mimetype="application/json",
            )

        taxes_list = [
            {
                "charge_type": charge.get("charge_type"),
                "account_head": charge.get("account_head"),
                "rate": charge.get("rate"),
                "description": charge.get("description"),
            }
            for charge in pos_settings.get("sales_taxes_and_charges")
        ]

        invoice_items = [
            {
                "item_code": (
                    item["item_code"]
                    if frappe.get_value("Item", {"name": item["item_code"]}, "name")
                    else None
                ),
                "qty": item.get("quantity", 0),
                "rate": item.get("rate", 0),
                "uom": item.get("uom", "Nos"),
                "income_account":pos_settings.income_account,
                "item_tax_template":pos_settings.item_tax_template,
            }
            for item in items
        ]

        payment_items = [
        {
            "mode_of_payment": payment.get("mode_of_payment", "Cash"),
            "amount": float(payment.get("amount", 0)),
        }
        for payment in payments or []
    ]


        if pos_settings.post_to_pos_invoice and pos_settings.post_to_sales_invoice:
            return Response(
                json.dumps(
                    {
                        "data": "Both POS Invoice and Sales Invoice creation are enabled. Please enable only one."
                    }
                ),
                status=400,
                mimetype="application/json",
            )

        if pos_settings.post_to_pos_invoice:
            doctype = "POS Invoice"
            pos_sync_id = frappe.get_all(
                "POS Invoice",
                ["name"],
                filters={"custom_unique_id": ["like", unique_id]},
            )
            if pos_sync_id:
                return Response(
                    json.dumps(
                        {
                            "data": "A duplicate entry was detected, unique ID already exists."
                        }
                    ),
                    status=409,
                    mimetype="application/json",
                )
        elif pos_settings.post_to_sales_invoice:
            doctype = "Sales Invoice"
            sales_sync_id = frappe.get_all(
                "Sales Invoice",
                ["name"],
                filters={"custom_unique_id": ["like", unique_id]},
            )

            if sales_sync_id:
                return Response(
                    json.dumps(
                        {
                            "data": "A duplicate entry was detected, unique ID already exists."
                        }
                    ),
                    status=409,
                    mimetype="application/json",
                )
        else:
            return Response(
                json.dumps(
                    {
                        "data": "Neither POS Invoice nor Sales Invoice creation is enabled in settings."
                    }
                ),
                status=400,
                mimetype="application/json",
            )

        new_invoice = frappe.get_doc(
            {
                "doctype": doctype,
                "customer": customer_name,
                "custom_unique_id": unique_id,
                "discount_amount": discount_amount,
                "items": invoice_items,
                "payments": payment_items,
                "taxes": taxes_list,
                "po_no": Customer_Purchase_Order,
                "custom_zatca_pos_name": machine_name,
            }
        )

        new_invoice.insert(ignore_permissions=True)
        new_invoice.save()

        uploaded_files = frappe.request.files
        xml_url, qr_code_url = None, None
        if "xml" in uploaded_files:
            new_invoice.custom_xml = process_file_upload(
                uploaded_files["xml"], ignore_permissions=True, is_private=True
            )
        if "qr_code" in uploaded_files:
            new_invoice.custom_qr_code = process_file_upload(
                uploaded_files["qr_code"], ignore_permissions=True, is_private=True
            )

        new_invoice.save(ignore_permissions=True)
        new_invoice.submit()
        frappe.db.set_value("Zatca Multiple Setting", "n9va72eppu", "custom_pih", PIH)

        doc = frappe.get_doc("Zatca Multiple Setting", "n9va72eppu")

        doc.save()
        template = frappe.get_doc("Item Tax Template", new_invoice.items[0].item_tax_template)
        item_tax_rate = None

        if template.taxes:
            # Assuming you want the first tax entry's rate
           item_tax_rate = template.taxes[0].tax_rate


        response_data = {
            "id": new_invoice.name,
            "customer_id": new_invoice.customer,
            "unique_id": new_invoice.custom_unique_id,
            "customer_name": new_invoice.customer_name,
            "total_quantity": new_invoice.total_qty,
            "total": new_invoice.total,
            "grand_total": new_invoice.grand_total,
            "Customer's Purchase Order": (
                int(new_invoice.po_no) if new_invoice.po_no else None
            ),
            "discount_amount": new_invoice.discount_amount,
            "xml": (
                new_invoice.custom_xml if hasattr(new_invoice, "custom_xml") else None
            ),
            "qr_code": (
                new_invoice.custom_qr_code
                if hasattr(new_invoice, "custom_qr_code")
                else None
            ),
            "pih": doc.custom_pih,
            "items": [
                {
                    "item_name": item.item_name,
                    "item_code": item.item_code,
                    "quantity": item.qty,
                    "rate": item.rate,
                    "uom": item.uom,
                    "income_account": item.income_account,
                    "item_tax_template": item.item_tax_template,
                    "tax_rate": item_tax_rate,
                }
                for item in new_invoice.items
            ],
            "taxes": [
                {
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "tax_rate": tax.rate,
                    "total": tax.total,
                    "description": tax.description,
                }
                for tax in new_invoice.taxes
            ],
            # "payments": [
            #     {
            #         "mode_of_payment": payment.mode_of_payment,
            #         "amount": payment.amount,
            #     }
            #     for payment in new_invoice.payments
            # ],
        }

        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except ValidationError as ve:

        error_message = str(ve)


        if "Status code: 400" in error_message:
            return Response(
                json.dumps({"message": error_message}),
                status=400,
                mimetype="application/json"
            )
        else:
            # default to 500 if not 400 specific
            return Response(
                json.dumps({"message": error_message}),
                status=500,
                mimetype="application/json"
            )

    except Exception as e:
        # Fallback for all other errors
        return Response(
            json.dumps({"message": str(e)}),
            status=500,
            mimetype="application/json"
        )
