from cmath import phase
import requests
import json
import frappe
import urllib.parse
import base64
from werkzeug.wrappers import Response
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password
from frappe.utils.image import optimize_image
from mimetypes import guess_type
from frappe.utils import now_datetime, cint
from datetime import datetime, timedelta
from frappe.utils import today
from frappe import _
from frappe import ValidationError


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
def generate_token_for_offline_user(api_key, api_secret, app_key):
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
def get_items(item_group=None, last_updated_time=None):

    from datetime import datetime

    fields = ["name", "stock_uom", "item_name", "item_group", "description", "modified"]
    # filters = {"item_group": ["like", f"%{item_group}%"]} if item_group else {}
    item_filters = {}
    if item_group:
        item_filters["item_group"] = ["like", f"%{item_group}%"]

    item_codes_set = set()

    if last_updated_time:
        try:
            last_updated_dt = datetime.strptime(last_updated_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return Response(
                json.dumps(
                    {"error": "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS"}
                ),
                status=400,
                mimetype="application/json",
            )

        # Get items modified after last_updated_time
        modified_item_filters = item_filters.copy()
        modified_item_filters["modified"] = [">", last_updated_dt]
        modified_items = frappe.get_all(
            "Item", fields=["name"], filters=modified_item_filters
        )
        item_codes_set.update([item["name"] for item in modified_items])

        # Get item codes from modified Item Price
        price_items = frappe.get_all(
            "Item Price",
            fields=["item_code"],
            filters={"modified": [">", last_updated_dt]},
        )
        item_codes_set.update([p["item_code"] for p in price_items])

        if not item_codes_set:
            return Response(
                json.dumps({"data": []}), status=200, mimetype="application/json"
            )

        item_filters["name"] = ["in", list(item_codes_set)]
    items = frappe.get_all("Item", fields=fields, filters=item_filters)
    item_meta = frappe.get_meta("Item")
    has_arabic = "custom_item_name_arabic" in [df.fieldname for df in item_meta.fields]
    has_english = "custom_item_name_in_english" in [
        df.fieldname for df in item_meta.fields
    ]

    grouped_items = {}

    for item in items:
        item_doc = frappe.get_doc("Item", item.name)

        # Determine English and Arabic names
        item_name_arabic = ""
        item_name_english = ""

        if has_arabic and item_doc.get("custom_item_name_arabic"):
            item_name_arabic = item_doc.custom_item_name_arabic
            item_name_english = item.item_name
        elif has_english and item_doc.get("custom_item_name_in_english"):
            item_name_arabic = item.item_name
            item_name_english = item_doc.custom_item_name_in_english

        uoms = frappe.get_all(
            "UOM Conversion Detail",
            filters={"parent": item.name},
            fields=[
                "name",
                "uom",
                "conversion_factor",
            ],
        )
        barcodes = frappe.get_all(
            "Item Barcode",
            filters={"parent": item.name},
            fields=[
                "name",
                "barcode",
                "uom",
                "custom_editable_price",
                "custom_editable_quantity",
            ],
        )
        item_prices = frappe.get_all(
            "Item Price",
            fields=["price_list_rate", "uom", "creation"],
            filters={
                "item_code": item.name,
                "price_list": "Standard Selling",
            },
            order_by="creation",  # fix item.item_code to item.name
        )

        # Build a mapping of UOM -> price
        price_map = {price.uom: price.price_list_rate for price in item_prices}
        barcode_map = {}
        for barcode in barcodes:
            if barcode.uom in barcode_map:
                barcode_map[barcode.uom].append(barcode.barcode)
            else:
                barcode_map[barcode.uom] = [barcode.barcode]

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
                "item_name_english": item_name_english,
                "item_name_arabic": item_name_arabic,
                "tax_percentage": (item.get("custom_tax_percentage") or 0.0),
                "description": item.description,
                "barcodes": [
                    {
                        "id": barcode.name,
                        "barcode": barcode.barcode,
                        "uom": barcode.uom,
                    }
                    for barcode in barcodes
                ],
                "uom": [
                    {
                        "id": uom.name,  # assuming 'name' is the item_code here
                        "uom": uom.uom,
                        "conversion_factor": uom.conversion_factor,
                        "price": round(price_map.get(uom.uom, 0.0), 2),
                        "barcode": ", ".join(barcode_map.get(uom.uom, [])),
                        "editable_price": bool(
                            frappe.get_value("UOM", uom.uom, "custom_editable_price")
                        ),
                        "editable_quantity": bool(
                            frappe.get_value("UOM", uom.uom, "custom_editable_quantity")
                        ),
                        # fetch price for this uom
                    }
                    for uom in uoms
                ],
            }
        )

    result = list(grouped_items.values())
    return Response(
        json.dumps({"data": result}), status=200, mimetype="application/json"
    )


@frappe.whitelist(allow_guest=True)
def get_items_page(item_group=None, last_updated_time=None, limit=50, offset=0):
    import json
    from datetime import datetime

    # from werkzeug.wrappers import Response

    fields = ["name", "stock_uom", "item_name", "item_group", "description", "modified"]
    item_filters = {}
    if item_group:
        item_filters["item_group"] = ["like", f"%{item_group}%"]

    item_codes_set = set()

    if last_updated_time:
        try:
            last_updated_dt = datetime.strptime(last_updated_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return Response(
                json.dumps(
                    {"error": "Invalid datetime format. Use YYYY-MM-DD HH:MM:SS"}
                ),
                status=400,
                mimetype="application/json",
            )

        # Get items modified after last_updated_time
        modified_item_filters = item_filters.copy()
        modified_item_filters["modified"] = [">", last_updated_dt]
        modified_items = frappe.get_all(
            "Item", fields=["name"], filters=modified_item_filters
        )
        item_codes_set.update([item["name"] for item in modified_items])

        # Get item codes from modified Item Price
        price_items = frappe.get_all(
            "Item Price",
            fields=["item_code"],
            filters={"modified": [">", last_updated_dt]},
        )
        item_codes_set.update([p["item_code"] for p in price_items])

        if not item_codes_set:
            return Response(
                json.dumps({"data": []}), status=200, mimetype="application/json"
            )

        item_filters["name"] = ["in", list(item_codes_set)]

    # Convert limit and offset to integers
    try:
        limit = int(limit)
        offset = int(offset)
    except ValueError:
        return Response(
            json.dumps({"error": "Invalid limit or offset. Must be integers."}),
            status=400,
            mimetype="application/json",
        )

    items = frappe.get_all(
        "Item",
        fields=fields,
        filters=item_filters,
        limit_page_length=limit,
        limit_start=offset,
    )

    item_meta = frappe.get_meta("Item")
    has_arabic = "custom_item_name_arabic" in [df.fieldname for df in item_meta.fields]
    has_english = "custom_item_name_in_english" in [
        df.fieldname for df in item_meta.fields
    ]

    grouped_items = {}

    for item in items:
        item_doc = frappe.get_doc("Item", item.name)

        item_name_arabic = ""
        item_name_english = ""

        if has_arabic and item_doc.get("custom_item_name_arabic"):
            item_name_arabic = item_doc.custom_item_name_arabic
            item_name_english = item.item_name
        elif has_english and item_doc.get("custom_item_name_in_english"):
            item_name_arabic = item.item_name
            item_name_english = item_doc.custom_item_name_in_english

        uoms = frappe.get_all(
            "UOM Conversion Detail",
            filters={"parent": item.name},
            fields=["uom", "conversion_factor"],
        )
        barcodes = frappe.get_all(
            "Item Barcode",
            filters={"parent": item.name},
            fields=["barcode", "uom"],
        )
        item_prices = frappe.get_all(
            "Item Price",
            fields=["price_list_rate", "uom"],
            filters={"item_code": item.name},
        )

        price_map = {price["uom"]: price["price_list_rate"] for price in item_prices}
        # Group barcodes by UOM
        barcode_map = {}
        for barcode in barcodes:
            if barcode.uom in barcode_map:
                barcode_map[barcode.uom].append(barcode.barcode)
            else:
                barcode_map[barcode.uom] = [barcode.barcode]

        if item.item_group not in grouped_items:
            grouped_items[item.item_group] = {
                "item_group_id": item.item_group,
                "item_group": item.item_group,
                "items": [],
            }

        grouped_items[item.item_group]["items"].append(
            {
                "item_id": item.name,
                "item_code": item.name,
                "item_name": item.item_name,
                "item_name_english": item_name_english,
                "item_name_arabic": item_name_arabic,
                "tax_percentage": (item_doc.get("custom_tax_percentage") or 0.0),
                "description": item.description,
                "barcodes": [
                    {"barcode": barcode["barcode"], "uom": barcode["uom"]}
                    for barcode in barcodes
                ],
                "uom": [
                    {
                        "uom": uom["uom"],
                        "conversion_factor": uom["conversion_factor"],
                        "price": price_map.get(uom["uom"], 0.0),
                        "barcode": ", ".join(barcode_map.get(uom.uom, [])),
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
        fields=[
            "name as id",
            "mobile_no as phone_no",
            "customer_name",
            "custom_default_pos",
            "disabled",
        ],
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
    systemSettings = frappe.get_doc("Claudion POS setting")
    var = True if systemSettings.show_item == 1 else False
    Zatca_Multiple_Setting = (
        frappe.get_doc("ZATCA Multiple Setting", machine_name) if machine_name else None
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
    company = frappe.get_doc("Company", linked_doctype)
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
            ["Dynamic Link", "link_name", "=", company.name],
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
        "phase": zatca.custom_phase_1_or_2,
        "discount_field": systemSettings.discount_field,
        "prefix_included_or_not": systemSettings.prefix_included_or_not,
        "no_of_prefix_character": int(systemSettings.no_of_prefix_character),
        "prefix": systemSettings.prefix,
        "item_code_total_digits": int(systemSettings.item_code_total_digits),
        "item_code_starting_position": int(systemSettings.item_code_starting_position),
        "weight_starting_position": int(systemSettings.weight_starting_position),
        "weight_total_digits_excluding_decimal": int(
            systemSettings.weight_total_digitsexcluding_decimal
        ),
        "no_of_decimal_in_weights": int(systemSettings.no_of_decimal_in_weights),
        "price_included_in_barcode_or_not": int(
            systemSettings.price_included_in_barcode_or_not
        ),
        "price_starting_position": int(systemSettings.price_starting_position),
        "price_total_digits_excluding_decimals": int(
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
        "company_name_in_arabic": systemSettings.company_name_in_arabic,
        "taxes": [
            {
                "charge_type": tax.charge_type,
                "account_head": tax.account_head,
                "tax_rate": tax.rate,
                "total": tax.total,
                "description": tax.description,
                "included_in_paid_amount": 1,
                "included_in_print_rate": 1,
            }
            for tax in systemSettings.sales_taxes_and_charges
        ],
        "zatca": {
            "company_name": zatca.name,
            "phase": zatca.custom_phase_1_or_2,
            "company_taxid": zatca.tax_id,
            "certificate": encoded_certificate,
            "pih": (
                (
                    Zatca_Multiple_Setting.custom_pih
                    if Zatca_Multiple_Setting
                    else zatca.custom_pih
                )
                if zatca.custom_phase_1_or_2 == "Phase-2"
                else None
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

    filters = {"name": ["like", f"%{id}%"]} if id else {}

    pos_invoices = frappe.get_list("POS Invoice", fields=["name"], filters=filters)

    all_items_with_warehouse_details = []

    for invoice in pos_invoices:

        items = frappe.get_all(
            "POS Invoice Item",
            fields=["item_code", "warehouse"],
            filters={"parent": invoice["name"]},
        )

        for item in items:

            if item["warehouse"]:
                try:

                    warehouse_details = frappe.get_doc("Warehouse", item["warehouse"])

                    item_with_details = {
                        "id": invoice["name"],
                        "item_code": item["item_code"],
                        "warehouse": item["warehouse"],
                        "mobile_no": getattr(warehouse_details, "mobile_no", None),
                        "address_line": getattr(
                            warehouse_details, "address_line_1", None
                        ),
                    }

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

        client_id = clientID
        client_secret = clientSecret
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
        systemSettings = frappe.get_doc("Claudion POS setting")
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

        return Response(
            json.dumps({"message": e, "user_count": 0}),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=True)
def getOfflinePOSUsers(id=None, offset=0, limit=50):

    docs = frappe.db.get_all(
        "POS Offline Users",
        fields=[
            "name",
            "offine_username",
            "shop_name",
            "password",
            "custom_cashier_name",
            "user as actual_user_name",
            "branch_address",
            "printe_template as print_template",  # Text Editor field
            "custom_print_format",
            "custom_is_admin",  # Link to Print Format
        ],
        order_by="offine_username",
        limit_start=offset,
        limit_page_length=limit,
    )

    for doc in docs:
        # Decrypt and encode password
        decrypted_password = get_decrypted_password(
            "POS Offline Users", doc.name, "password"
        )
        doc["password"] = base64.b64encode(decrypted_password.encode("utf-8")).decode(
            "utf-8"
        )

        # Get POS Profiles for the user
        pos_profiles = frappe.db.get_all(
            "POS Profile User",
            filters={"user": doc["actual_user_name"]},
            fields=["parent as pos_profile"],
        )
        doc["pos_profiles"] = [p["pos_profile"] for p in pos_profiles]

        # Determine the correct print_format value
        if doc.get("print_template"):
            doc["print_template"] = doc["print_template"]
        elif doc.get("custom_print_format"):
            html = frappe.db.get_value(
                "Print Format", doc["custom_print_format"], "html"
            )
            doc["print_template"] = html
        else:
            doc["print_template"] = None

        # Clean up if needed
        # doc.pop("print_template", None)
        # doc.pop("custom_print_format", None)
        doc["custom_is_admin"] = bool(doc.get("custom_is_admin", 0))

    return Response(json.dumps({"data": docs}), status=200, mimetype="application/json")


@frappe.whitelist(allow_guest=True)
def create_invoice_unsynced(date_time, invoice_number, clearing_status):
    try:
        doc = frappe.get_doc(
            {
                "doctype": "Invoice Unsynced",
                "date_time": date_time,
                "invoice_number": invoice_number,
                "clearing_status": clearing_status,
            }
        )
        doc.insert()
        frappe.db.commit()
        return {
            "status": "success",
            "message": "Invoice Unsynced created",
            "name": doc.name,
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API: create_invoice_unsynced")
        return {"status": "error", "message": str(e)}


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


@frappe.whitelist(allow_guest=False)
def create_invoice(
    customer_name,
    items,
    machine_name,
    Customer_Purchase_Order=None,
    payments=None,
    discount_amount=None,
    unique_id=None,
    custom_offline_creation_time=None,  # ✅ New param
    offline_invoice_number=None,  # ✅ New param
    pos_profile=None,
    pos_shift=None,
    cashier=None,
    PIH=None,
    phase=2,
):  # Default to phase 1
    try:

        pos_settings = frappe.get_doc("Claudion POS setting")

        items = parse_json_field(frappe.form_dict.get("items"))
        payments = parse_json_field(frappe.form_dict.get("payments"))
        discount_amount = float(frappe.form_dict.get("discount_amount", 0))
        Customer_Purchase_Order = frappe.form_dict.get("Customer_Purchase_Order")
        unique_id = frappe.form_dict.get("unique_id")
        PIH = frappe.form_dict.get("PIH")
        offline_invoice_number = frappe.form_dict.get("offline_invoice_number")  # k  ✅
        pos_profile = frappe.form_dict.get("pos_profile")
        pos_shift = frappe.form_dict.get("pos_shift")
        cashier = frappe.form_dict.get("cashier")
        for item in items:
            item["rate"] = float(item.get("rate", 0))
            item["quantity"] = float(item.get("quantity", 0))

        for payment in payments or []:
            payment["amount"] = float(payment.get("amount", 0))

        customer_details = frappe.get_all(
            "Customer",
            fields=["name"],
            filters={"name": ["like", customer_name]},
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
                "included_in_paid_amount": 1,
                "included_in_print_rate": 0,
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
                "income_account": pos_settings.income_account,
                "item_tax_template": pos_settings.item_tax_template,
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
        cost_center = None
        if pos_profile:
            pos_doc = frappe.get_doc("POS Profile", pos_profile)
            cost_center = pos_doc.cost_center

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
                "is_pos": 1,
                "custom_offline_creation_time": custom_offline_creation_time,
                "custom_offline_invoice_number": offline_invoice_number,
                "pos_profile": pos_profile,
                "posa_pos_opening_shift": pos_shift,
                "custom_cashier": cashier,
                "cost_center": cost_center,
            }
        )

        new_invoice.insert(ignore_permissions=True)
        new_invoice.save()

        uploaded_files = frappe.request.files
        xml_url, qr_code_url = None, None
        if phase == 2:
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
        zatca_setting_name = pos_settings.zatca_multiple_setting
        if PIH:
            frappe.db.set_value(
                "ZATCA Multiple Setting", zatca_setting_name, "custom_pih", PIH
            )

        doc = frappe.get_doc("ZATCA Multiple Setting", zatca_setting_name)

        doc.save()
        template = frappe.get_doc(
            "Item Tax Template", new_invoice.items[0].item_tax_template
        )
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
            "pih": doc.custom_pih if PIH else None,
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
                    "included_in_paid_amount": tax.get("included_in_paid_amount", 1),
                    "included_in_print_rate": tax.get("included_in_print_rate", 1),
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
                mimetype="application/json",
            )
        else:
            # default to 500 if not 400 specific
            return Response(
                json.dumps({"message": error_message}),
                status=500,
                mimetype="application/json",
            )

    except Exception as e:
        # Fallback for all other errors
        return Response(
            json.dumps({"message": str(e)}), status=500, mimetype="application/json"
        )


# your_app/api/pos_offer_api.py


@frappe.whitelist()
def get_pos_offers():
    filters = {
        "docstatus": 0,
        "disable": 0,
        "valid_from": ["<=", today()],
        "valid_upto": [">=", today()],
    }

    offers = frappe.get_all(
        "POS Offer",
        filters=filters,
        fields=[
            "name",
            "title",
            "description",
            "discount_type",
            "discount_amount",
            "discount_percentage",
            "item",
            "min_qty",
            "max_qty",
            "min_amt",
            "max_amt",
            "apply_on",
            "offer",
            "company",
            "warehouse",
            "pos_profile",
            "valid_from",
            "valid_upto",
            "auto",
        ],
    )

    return offers


@frappe.whitelist(allow_guest=True)
def sync_gpos_log(details, datetime, location, sync_id):
    try:
        # Check for existing record with the same sync_id
        existing = frappe.db.exists("gpos logs", {"sync_id": sync_id})
        if existing:
            frappe.local.response.http_status_code = 409  # Confl ict
            response_data = {
                "status": "conflict",
                "message": f"Log with sync_id '{sync_id}' already exists.",
                "name": existing,
                "sync_id": sync_id,
            }
            return Response(
                json.dumps({"data": response_data}),
                status=409,
                mimetype="application/json",
            )

        doc = frappe.get_doc(
            {
                "doctype": "gpos logs",
                "details": details,
                "fatetime": datetime,
                "location": location,
                "sync_id": sync_id,
            }
        )
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        response_data = {"status": "success", "name": doc.name, "sync_id": sync_id}
        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "sync_gpos_log Error")
        frappe.local.response.http_status_code = 500
        error_data = {"status": "error", "message": str(e), "sync_id": sync_id}
        return Response(
            json.dumps({"data": error_data}), status=500, mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def get_shift_status(shift_id):
    """
    API to fetch the status of a POS Opening or Closing Shift by its shift ID.
    """
    try:
        if not shift_id:
            return Response(
                json.dumps({"error": "Missing shift_id parameter."}),
                status=400,
                mimetype="application/json",
            )

        # Try fetching POS Opening or Closing Shift
        if frappe.db.exists("POS Opening Shift", shift_id):
            doc = frappe.get_doc("POS Opening Shift", shift_id)
        elif frappe.db.exists("POS Closing Shift", shift_id):
            doc = frappe.get_doc("POS Closing Shift", shift_id)
        else:
            return Response(
                json.dumps({"error": f"No POS Shift found with ID: {shift_id}"}),
                status=404,
                mimetype="application/json",
            )

        response_data = {"shift_id": doc.name, "status": doc.get("status", "Unknown")}

        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Shift Status Error")

        return Response(
            json.dumps(
                {"error": "Failed to retrieve shift status.", "details": str(e)}
            ),
            status=500,
            mimetype="application/json",
        )


@frappe.whitelist(allow_guest=False)
def create_credit_note(
    customer_name,
    items,
    PIH,
    machine_name,
    payments=None,
    discount_amount=None,
    unique_id=None,
    offline_invoice_number=None,
    pos_profile=None,
    pos_shift=None,
    cashier=None,
    return_against=None,
    reason=None,
):

    try:
        pos_settings = frappe.get_doc("Claudion POS setting")

        items = parse_json_field(frappe.form_dict.get("items"))
        payments = parse_json_field(frappe.form_dict.get("payments"))
        discount_amount = float(frappe.form_dict.get("discount_amount", 0))
        unique_id = frappe.form_dict.get("unique_id")
        PIH = frappe.form_dict.get("PIH")
        offline_invoice_number = frappe.form_dict.get("offline_invoice_number")
        pos_profile = frappe.form_dict.get("pos_profile")
        pos_shift = frappe.form_dict.get("pos_shift")
        cashier = frappe.form_dict.get("cashier")
        return_against = frappe.form_dict.get("return_against")
        reason = frappe.form_dict.get("reason")

        for item in items:
            item["rate"] = float(item.get("rate", 0))
            item["quantity"] = float(item.get("quantity", 0))

        for payment in payments or []:
            payment["amount"] = float(payment.get("amount", 0))

        customer_details = frappe.get_all(
            "Customer",
            fields=["name"],
            filters={"name": ["like", customer_name]},
        )
        if not customer_details:
            return Response(
                json.dumps({"data": "Customer name not found"}),
                status=404,
                mimetype="application/json",
            )

        if not return_against:
            return Response(
                json.dumps(
                    {"data": "Missing 'return_against' parameter for credit note."}
                ),
                status=400,
                mimetype="application/json",
            )

        if not frappe.db.exists("Sales Invoice", return_against):
            return Response(
                json.dumps({"data": f"Sales Invoice {return_against} not found"}),
                status=404,
                mimetype="application/json",
            )

        # ✅ Prevent duplicate return based on unique_id
        if unique_id:
            existing_return = frappe.db.exists(
                "Sales Invoice",
                {"custom_unique_id": unique_id, "is_return": 1, "docstatus": 1},
            )
            if existing_return:
                return Response(
                    json.dumps(
                        {
                            "data": f"Credit note already created with unique_id {unique_id}"
                        }
                    ),
                    status=409,
                    mimetype="application/json",
                )

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
                "income_account": pos_settings.income_account,
                "item_tax_template": pos_settings.item_tax_template,
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
        cost_center = None
        if pos_profile:
            pos_doc = frappe.get_doc("POS Profile", pos_profile)
            cost_center = pos_doc.cost_center

        new_invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "customer": customer_name,
                "custom_unique_id": unique_id,
                "discount_amount": discount_amount,
                "items": invoice_items,
                "payments": payment_items,
                "custom_zatca_pos_name": machine_name,
                "is_pos": 1,
                "is_return": 1,
                "return_against": return_against,
                "custom_offline_invoice_number": offline_invoice_number,
                "pos_profile": pos_profile,
                "posa_pos_opening_shift": pos_shift,
                "custom_cashier": cashier,
                "custom_reason": reason,
                "cost_center": cost_center,
            }
        )

        new_invoice.insert(ignore_permissions=True)
        new_invoice.save()

        uploaded_files = frappe.request.files
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

        # Update PIH value
        zatca_setting_name = pos_settings.zatca_multiple_setting
        frappe.db.set_value(
            "ZATCA Multiple Setting", zatca_setting_name, "custom_pih", PIH
        )

        doc = frappe.get_doc("ZATCA Multiple Setting", zatca_setting_name)
        doc.save()

        # Get item tax rate
        template = frappe.get_doc(
            "Item Tax Template", new_invoice.items[0].item_tax_template
        )
        item_tax_rate = template.taxes[0].tax_rate if template.taxes else None

        response_data = {
            "id": new_invoice.name,
            "customer_id": new_invoice.customer,
            "unique_id": new_invoice.custom_unique_id,
            "customer_name": new_invoice.customer_name,
            "total_quantity": new_invoice.total_qty,
            "total": new_invoice.total,
            "grand_total": new_invoice.grand_total,
            "discount_amount": new_invoice.discount_amount,
            "xml": getattr(new_invoice, "custom_xml", None),
            "qr_code": getattr(new_invoice, "custom_qr_code", None),
            "pih": doc.custom_pih,
            "return_against": new_invoice.return_against,
            "is_return": new_invoice.is_return,
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
        }

        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except ValidationError as ve:
        error_message = str(ve)
        return Response(
            json.dumps({"message": error_message}),
            status=400 if "Status code: 400" in error_message else 500,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            json.dumps({"message": str(e)}), status=500, mimetype="application/json"
        )


@frappe.whitelist(allow_guest=False)
def get_invoice_details(invoice_number):
    try:
        if not invoice_number:
            return Response(
                json.dumps({"message": "Invoice number is required."}),
                status=400,
                mimetype="application/json",
            )

        # Fetch the Sales Invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_number)

        if not invoice:
            return Response(
                json.dumps({"message": "Invoice not found."}),
                status=404,
                mimetype="application/json",
            )

        # Get tax rate from first item's tax template
        item_tax_rate = None
        if invoice.items and invoice.items[0].item_tax_template:
            template = frappe.get_doc(
                "Item Tax Template", invoice.items[0].item_tax_template
            )
            if template.taxes:
                item_tax_rate = template.taxes[0].tax_rate

        # Prepare response
        response_data = {
            "id": invoice.name,
            "customer_id": invoice.customer,
            "customer_name": invoice.customer_name,
            "posting_date": str(invoice.posting_date),
            "total_quantity": invoice.total_qty,
            "total": invoice.total,
            "grand_total": invoice.grand_total,
            "discount_amount": invoice.discount_amount,
            "po_no": invoice.po_no,
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
                for item in invoice.items
            ],
            "taxes": [
                {
                    "charge_type": tax.charge_type,
                    "account_head": tax.account_head,
                    "tax_rate": tax.rate,
                    "total": tax.total,
                    "description": tax.description,
                    "included_in_paid_amount": tax.included_in_paid_amount,
                    "included_in_print_rate": tax.included_in_print_rate,
                }
                for tax in invoice.taxes
            ],
            "payments": [
                {
                    "mode_of_payment": p.mode_of_payment,
                    "amount": p.amount,
                }
                for p in invoice.payments
            ],
            "offline_invoice_number": invoice.custom_offline_invoice_number,
            "offline_creation_time": (
                str(invoice.custom_offline_creation_time)
                if invoice.custom_offline_creation_time
                else None
            ),
            "xml": invoice.custom_xml if hasattr(invoice, "custom_xml") else None,
            "qr_code": (
                invoice.custom_qr_code if hasattr(invoice, "custom_qr_code") else None
            ),
        }

        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except frappe.DoesNotExistError:
        return Response(
            json.dumps({"message": "Invoice not found."}),
            status=404,
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"message": str(e)}), status=500, mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def get_promotion_list(pos_profile):
    try:
        if not frappe.db.exists("POS Profile", pos_profile):
            return Response(
                json.dumps({"error": "POS Profile not found"}),
                status=404,
                mimetype="application/json",
            )

        today = datetime.today().date()

        promotions = frappe.get_all(
            "promotion",
            filters={"valid_upto": (">=", today)},
            fields=["name", "company", "valid_from", "valid_upto"],
        )

        result = []
        linked_to_any_promotion = False

        for promo in promotions:
            doc = frappe.get_doc("promotion", promo.name)
            pos_profiles = [row.pos_profile for row in doc.pos_profile_table]

            if pos_profile not in pos_profiles:
                continue

            linked_to_any_promotion = True

            item_table = []
            for item in doc.item_table:
                item_doc = frappe.get_doc("Item", item.item_code)

                # Find the child UOM row where uom == item.uom
                matched_uom_row = None
                for uom_row in item_doc.uoms:
                    if uom_row.uom == item.uom:
                        matched_uom_row = uom_row
                        break

                item_table.append(
                    {
                        "id": item.name,
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "discount_type": (
                            "PERCENTAGE"
                            if item.discount_type == "Discount Percentage"
                            else (
                                "AMOUNT"
                                if item.discount_type == "Discount Amount"
                                else (
                                    "RATE"
                                    if item.discount_type == "Rate"
                                    else item.discount_type
                                )
                            )
                        ),
                        "min_qty": item.min_qty,
                        "max_qty": item.max_qty,
                        "discount_percentage": item.discount_percentage,
                        "discount_price": item.discount__amount,
                        "uom_id": matched_uom_row.name if matched_uom_row else None,
                        "uom": item.uom,
                    }
                )

            profile_doc = frappe.get_doc("POS Profile", pos_profile)

            result.append(
                {
                    "id": doc.name,
                    "company": doc.company,
                    "disabled": profile_doc.disabled,
                    "valid_from": str(doc.valid_from),
                    "valid_upto": str(doc.valid_upto),
                    "items": item_table,
                }
            )

        if not linked_to_any_promotion:
            return Response(
                json.dumps(
                    {"error": "This POS Profile is not linked to any promotions"}
                ),
                status=404,
                mimetype="application/json",
            )

        return Response(
            json.dumps({"data": result}, default=str),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_promotion_list error")
        return Response(
            json.dumps({"error": str(e)}),
            status=500,
            mimetype="application/json",
        )
