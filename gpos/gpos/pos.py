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
from frappe.utils import add_days, getdate

from datetime import datetime
BACKEND_SERVER_SETTINGS = "Backend Server Settings"
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
def get_items(item_group=None, last_updated_time=None, pos_profile = None):


    try:
        item_filters = {}
        pos_item_groups = []
        if pos_profile:
            pos = frappe.get_doc("POS Profile", pos_profile)
            pos_item_groups = [d.item_group for d in pos.item_groups]


            if pos_item_groups:
                item_filters["item_group"] = ["in", pos_item_groups]


        fields = ["name", "stock_uom", "item_name", "item_group", "description", "modified","disabled"]
        # filters = {"item_group": ["like", f"%{item_group}%"]} if item_group else {}

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


            modified_item_filters = item_filters.copy()
            modified_item_filters["modified"] = [">", last_updated_dt]

            modified_items = frappe.get_all(
                "Item", fields=["name"], filters=modified_item_filters
            )
            item_codes_set.update([item["name"] for item in modified_items])


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
            # Commented by Farook to send disabled tag on api, to handle from offline side properly
            # if item.disabled == 1:
            #     continue

            item_group_disabled = frappe.db.get_value(
                "Item Group", item.item_group, "custom_disabled"
            )


            if item.item_group not in grouped_items:
                grouped_items[item.item_group] = {
                    "item_group_id": item.item_group,
                    "item_group": item.item_group,
                    "item_group_disabled": bool(item_group_disabled),
                    "items": [] if not item_group_disabled else [],
                    "disabled": item.disabled,
                }

            if not item_group_disabled:
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
                    fields=["name", "uom", "conversion_factor"],
                )

                barcodes = frappe.get_all(
                    "Item Barcode",
                    filters={"parent": item.name},
                    fields=["name", "barcode", "uom", "custom_editable_price", "custom_editable_quantity"],
                )

                price_list = "Retail Price"
                if pos_profile:
                    price_list = frappe.db.get_value(
                        "POS Profile", pos_profile, "selling_price_list"
                    ) or "Retail Price"

                item_prices = frappe.get_all(
                    "Item Price",
                    fields=["price_list_rate", "uom", "creation"],
                    filters={"item_code": item.name, "price_list": price_list},
                    order_by="creation",
                )

                price_map = {price.uom: price.price_list_rate for price in item_prices}
                barcode_map = {}
                for barcode in barcodes:
                    if barcode.uom in barcode_map:
                        barcode_map[barcode.uom].append(barcode.barcode)
                    else:
                        barcode_map[barcode.uom] = [barcode.barcode]

                grouped_items[item.item_group]["items"].append(
                    {
                        "item_id": item.name,
                        "item_code": item.name,
                        "item_name": item.item_name,
                        "item_name_english": item_name_english,
                        "item_name_arabic": item_name_arabic,
                        "tax_percentage": (item.get("custom_tax_percentage") or 0.0),
                        "description": item.description,
                        "disabled": item.disabled,
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
                                "id": uom.name,
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
                            }
                            for uom in uoms
                        ],
                    }
                )
        result = list(grouped_items.values())


        if not result:
            return Response(
            json.dumps({"error": "No items found"}),
            status=404,
            mimetype="application/json"
        )

        return Response(
            json.dumps({"data": result}),
            status=200,
            mimetype="application/json"
        )
    except Exception as e:
        return Response(
            json.dumps({"error":e}),
            status=404,
            mimetype="application/json"
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
    customer_name, lead_name,pos_profile=None, email_id=None, gender=None, mobile_no=None,
):
    try:
        lead = frappe.get_all(
            "Lead", fields=["lead_name"], filters={"name": ["like", f"{lead_name}"]}
        )

        if lead:

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

            existing_customer.save(ignore_permissions=True)
            frappe.db.commit()
            return Response(
                json.dumps({"data": "Customer updated successfully"}),
                status=200,
                mimetype="application/json",
            )
        else:

            doc = frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": customer_name,
                    "mobile_no": mobile_no,
                    "lead_name": lead_name,
                    "email_id": email_id,
                    "gender": gender,

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

        pass

@frappe.whitelist(allow_guest=True)
def customer_list_old(id=None, pos_profile=None):
    #Please use the new new customer_list - Farook
    try:

        filters = {"name": ["like", f"{id}"]} if id else None

        customers = frappe.get_list(
            "Customer",
            fields=[
                "name as id",
                "mobile_no as phone_no",
                "customer_name",
                "custom_default_pos",
                "disabled",
            ],
            filters=filters,
        )


        if  not customers:
            return Response(
                json.dumps({"error": "Customer not found"}),
                status=404,
                mimetype="application/json",
            )


        if not pos_profile:
            return Response(
                json.dumps({"data": customers}),
                status=200,
                mimetype="application/json",
            )


        if not frappe.db.exists("POS Profile", pos_profile):
            return Response(
                json.dumps({"error": "POS Profile not found"}),
                status=404,
                mimetype="application/json",
            )

        default_customer = frappe.db.get_value("POS Profile", pos_profile, "customer")

        filtered_customers = []
        for cust in customers:

            if default_customer and cust["id"] == default_customer:
                cust["custom_default_pos"] = 1
                filtered_customers.append(cust)
                continue
            cust["custom_default_pos"] = 0

            pos_profiles = frappe.get_all(
                "pos profile child table",
                filters={"parent": cust["id"]},
                fields=["pos_profile"],
            )

            if not pos_profiles:
                filtered_customers.append(cust)
            else:
                if any(p["pos_profile"] == pos_profile for p in pos_profiles):
                    filtered_customers.append(cust)

        return Response(
            json.dumps({"data": filtered_customers}),
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        return Response(
            json.dumps({"error": f"Server error: {str(e)}"}),
            status=500,
            mimetype="application/json",
        )


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
def pos_setting(machine_name, pos_profile=None):
    systemSettings = frappe.get_doc("Claudion POS setting")
    var = True if systemSettings.show_item == 1 else False
    Zatca_Multiple_Setting = (
        frappe.get_doc("ZATCA Multiple Setting", machine_name) if machine_name else None
    )
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

    use_company_values = (
        Zatca_Multiple_Setting.custom__use_company_certificate__keys
        if Zatca_Multiple_Setting else False
    )

    if use_company_values:

        certificate = zatca.custom_certificate
        private_key = zatca.custom_private_key
        public_key = zatca.custom_public_key
        pih=zatca.custom_pih

    else:

        pih=Zatca_Multiple_Setting.custom_pih
        certificate = Zatca_Multiple_Setting.custom_certficate
        private_key = Zatca_Multiple_Setting.custom_private_key
        public_key = Zatca_Multiple_Setting.custom_public_key


    encoded_certificate = base64.b64encode(certificate.encode("utf-8")).decode("utf-8")
    encoded_private_key = base64.b64encode(private_key.encode("utf-8")).decode("utf-8")
    encoded_public_key = base64.b64encode(public_key.encode("utf-8")).decode("utf-8")

    address_record = address[0] if address else None

    pos_profile_doc = frappe.get_doc("POS Profile", pos_profile) if pos_profile else None
    address = pos_profile_doc.custom_address if pos_profile_doc else None
    address_details = frappe.get_doc("Address", address) if address else None
    card_pay=pos_profile_doc.custom_cardpay_settings if pos_profile_doc else None
    cardpay_setting=frappe.get_doc("CardPay Settings",card_pay) if card_pay else None

    branch_details = {
        "branch_name": pos_profile_doc.custom_branch if pos_profile_doc else None,
        "address1": address_details.address_line1 if address_details else None,
        "address2":address_details.address_line2 if address_details else None,
        "building_no":address_details.custom_building_number if address_details else None,
        "pb_no":address_details.pincode if address_details else None,
        "phone": int(address_details.phone) if address_details else None,
        "card_machine":bool(int(pos_profile_doc.custom_card_machine)) if pos_profile_doc and pos_profile_doc.custom_card_machine is not None else None
    } if pos_profile_doc else None

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
        "post_to_sales_invoice": systemSettings.post_to_sales_invoice,
        "post_to_pos_invoice": systemSettings.post_to_pos_invoice,
        "is_tax_included_in_price": systemSettings.is_tax_included_in_price,
        "tax_percentage": systemSettings.tax_percentage,
        "company_name_in_arabic": systemSettings.company_name_in_arabic,

        "cardpay_settings": {
            "id":cardpay_setting.name,
            "secret_key":cardpay_setting.secret_key,
            "api_key":cardpay_setting.api_key,
            "merchant_id":cardpay_setting.merchant_id,
            "connection_type":cardpay_setting.connection_type,
            "company":cardpay_setting.provider,
            "url":cardpay_setting.custom_url
        } if card_pay else None,
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
                pih
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
        "branch_details": branch_details,
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
def getOfflinePOSUsers(id=None, offset=0, limit=500):
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
def create_invoice_unsynced(date_time, invoice_number, clearing_status,type="Sales INvoice",manually_submitted=None,json_dump=None,api_response=None):
    try:
        sales_invoice = frappe.get_all(
            "Sales Invoice",
            fields=["name"],
            filters={"custom_offline_invoice_number": invoice_number},
            limit=1
        )

        if sales_invoice:
            clearing_status = 1

        doc = frappe.get_doc(
            {
                "doctype": "Invoice Unsynced",
                "date_time": date_time,
                "invoice_number": invoice_number,
                "clearing_status": clearing_status,
                "custom_json_dump": json_dump if json_dump else None,
                "custom_manually_submitted": manually_submitted if manually_submitted else 0,
                "custom_api_response": api_response if api_response else None,
                "custom_type" : type,
            }
        )
        doc.insert()
        frappe.db.commit()
        return {
            "status": "success",
            "message": "Invoice Unsynced created",
            "name": doc.name,
            "invoice_number": doc.invoice_number,
            "json_dump": doc.custom_json_dump,
            "manually_submitted": doc.custom_manually_submitted,
            "api_response": doc.custom_api_response,
            "type":doc.custom_type
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "API: create_invoice_unsynced")
        return Response(json.dumps({"status": "error", "message": str(e)}), status=500, mimetype="application/json")




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
    custom_offline_creation_time=None,
    offline_invoice_number=None,
    pos_profile=None,
    pos_shift=None,
    cashier=None,
    PIH=None,
    transaction_id=None,
    mobile_no=None,
    coupen_customer_name=None,

    phase=1,

):
    try:
        pos_settings = frappe.get_doc("Claudion POS setting")

        items = parse_json_field(frappe.form_dict.get("items"))
        payments = parse_json_field(frappe.form_dict.get("payments"))
        discount_amount = float(frappe.form_dict.get("discount_amount", 0))
        Customer_Purchase_Order = frappe.form_dict.get("Customer_Purchase_Order")
        unique_id = frappe.form_dict.get("unique_id")
        PIH = frappe.form_dict.get("PIH")
        offline_invoice_number = frappe.form_dict.get("offline_invoice_number")
        pos_profile = frappe.form_dict.get("pos_profile")
        pos_shift = frappe.form_dict.get("pos_shift")
        cashier = frappe.form_dict.get("cashier")

        for item in items:
            item["rate"] = float(item.get("rate", 0))
            item["quantity"] = float(item.get("quantity", 0))

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


        pos_profile_doc = (
            frappe.get_doc("POS Profile", pos_profile) if pos_profile else None
        )

        payment_items = []
        if payments:
            for payment in payments:
                mode = payment.get("mode_of_payment", "").strip()
                amount = float(payment.get("amount", 0))

                if mode.lower() in ["cash", "card"] and pos_profile:
                    for row in pos_profile_doc.get("payments") or []:
                        if (
                            row.custom_offline_mode_of_payment1
                            and row.custom_offline_mode_of_payment1.lower() == mode.lower()
                        ):
                            mode = row.mode_of_payment
                            break

                payment_items.append({"mode_of_payment": mode, "amount": amount})

        taxes_list = None

        if pos_profile:
            profile_cost_center = pos_profile_doc.cost_center
            profile_discount_account = pos_profile_doc.custom_discount_account
            if not pos_profile_doc.get("taxes_and_charges") and pos_settings.get(
                "sales_taxes_and_charges"
            ):
                taxes_list = [
                    {
                        "charge_type": tax.charge_type,
                        "account_head": tax.account_head,
                        "rate": tax.rate,
                        "description": tax.description,
                    }
                    for tax in pos_settings.get("sales_taxes_and_charges")
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
                "cost_center": item.get("cost_center", profile_cost_center),
                "discount_account": item.get("discount_account", profile_discount_account),
                "allow_zero_valuation_rate":1
            }
            for item in items
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

        if pos_settings.post_to_sales_invoice == 0:
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
            if offline_invoice_number:
                offline_invoice_no = frappe.get_all(
                    "Sales Invoice",
                    ["name"],
                    filters={"custom_offline_invoice_number": offline_invoice_number},
                )
                if offline_invoice_no:
                    return Response(
                        json.dumps(
                            {
                                "data": "A duplicate entry was detected, offline invoice number already exists."
                            }
                        ),
                        status=409,
                        mimetype="application/json",
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
        source_warehouse = None
        profile_taxes_and_charges = None
        profile_discount_account = None

        if pos_profile:
            pos_doc = frappe.get_doc("POS Profile", pos_profile)
            cost_center = pos_doc.cost_center
            source_warehouse = pos_doc.warehouse
            profile_taxes_and_charges = pos_doc.taxes_and_charges
            profile_discount_account = pos_doc.custom_discount_account

        new_invoice = frappe.get_doc(
            {
                "doctype": doctype,
                "customer": customer_name,
                "custom_unique_id": unique_id,
                "apply_discount_on": "Grand Total",
                "discount_amount": discount_amount,
                "items": invoice_items,
                "payments": payment_items,
                "po_no": Customer_Purchase_Order,
                "custom_zatca_pos_name": machine_name,
                # "disable_rounded_total" :0,
                "is_pos": 1,
                "custom_offline_creation_time": custom_offline_creation_time,
                "custom_offline_invoice_number": offline_invoice_number,
                "pos_profile": pos_profile,
                "posa_pos_opening_shift": pos_shift,
                "custom_cashier": cashier,
                "cost_center": cost_center,
                "update_stock": True,
                "set_warehouse": source_warehouse,
                "custom_invoice_type": "Retail",
                "taxes_and_charges": profile_taxes_and_charges,
                "additional_discount_account": profile_discount_account,
                "custom_transaction_id": transaction_id,
                "custom_coupon_customer_name":coupen_customer_name,
                "custom_loyalty_customer_mobile":mobile_no,
            }
        )

        if taxes_list:
            new_invoice["taxes"] = taxes_list

        uploaded_files = frappe.request.files
        xml_url, qr_code_url = None, None

        if phase == 2:
            if "xml" not in uploaded_files or "qr_code" not in uploaded_files:
                return Response(
                    json.dumps(
                        {
                            "message": "Both XML and QR code files are required in phase 2."
                        }
                    ),
                    status=400,
                    mimetype="application/json",
                )

            new_invoice.custom_xml = process_file_upload(
                uploaded_files["xml"], ignore_permissions=True, is_private=True
            )

            new_invoice.custom_qr_code = process_file_upload(
                uploaded_files["qr_code"], ignore_permissions=True, is_private=True
            )

        else:
            if "xml" in uploaded_files:
                new_invoice.custom_xml = process_file_upload(
                    uploaded_files["xml"], ignore_permissions=True, is_private=True
                )

            if "qr_code" in uploaded_files:
                new_invoice.custom_qr_code = process_file_upload(
                    uploaded_files["qr_code"], ignore_permissions=True, is_private=True
                )

        new_invoice.insert(ignore_permissions=True)
        new_invoice.submit()

        handle_loyalty_points(
            new_invoice.name,
            customer_name,
            mobile_no=mobile_no,
        )

        zatca_setting_name = pos_settings.zatca_multiple_setting
        if PIH:
            frappe.db.set_value(
                "ZATCA Multiple Setting", zatca_setting_name, "custom_pih", PIH
            )

        doc = frappe.get_doc("ZATCA Multiple Setting", zatca_setting_name)

        item_tax_rate = None

        response_data = {
            "id": new_invoice.name,
            "customer_id": new_invoice.customer,
            "unique_id": new_invoice.custom_unique_id,
            "customer_name": new_invoice.customer_name,
            "total_quantity": new_invoice.total_qty,
            "total": new_invoice.total,
            "net_total": new_invoice.net_total,
            "grand_total": new_invoice.grand_total,
            "Customer's Purchase Order": (
                int(new_invoice.po_no) if new_invoice.po_no else None
            ),
            "discount_amount": new_invoice.discount_amount,
            "xml": new_invoice.custom_xml if hasattr(new_invoice, "custom_xml") else None,
            "qr_code": new_invoice.custom_qr_code
            if hasattr(new_invoice, "custom_qr_code")
            else None,
            "pih": doc.custom_pih if PIH else None,
            "transaction_id":new_invoice.custom_transaction_id if transaction_id else None,
            "mobile_no":new_invoice.custom_loyalty_customer_mobile,
            "coupon_customer_name":new_invoice.custom_coupon_customer_name,
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
                    "allow_zero_valuation_rate":item.allow_zero_valuation_rate
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
                    "included_in_paid_amount": tax.get("included_in_paid_amount"),
                    "included_in_print_rate": tax.get("included_in_print_rate"),
                }
                for tax in new_invoice.taxes
            ],
        }

        return Response(
            json.dumps({"data": response_data}), status=200, mimetype="application/json"
        )

    except ValidationError as ve:
        error_message = str(ve)
        frappe.db.rollback()

        if "Status code: 400" in error_message:
            return Response(
                json.dumps({"message 400": error_message}),
                status=400,
                mimetype="application/json",
            )
        else:
            return Response(
                json.dumps({"message 500": error_message}),
                status=500,
                mimetype="application/json",
            )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Invoice API Error")
        frappe.db.rollback()
        return Response(
            json.dumps({"message Fallback 500": str(e)}),
            status=500,
            mimetype="application/json",
        )


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


        # if not return_against:
        #     return Response(
        #         json.dumps(
        #             {"data": "Missing 'return_against' parameter for credit note."}
        #         ),
        #         status=400,
        #         mimetype="application/json",
        #     )
        cost_center = None
        source_warehouse = None
        profile_taxes_and_charges = None
        return_invoice = frappe.db.exists("Sales Invoice", return_against)
        offline_no_invoice_id = None
        if not return_invoice:
            offline_no_invoice_id = frappe.db.get_value(
                "Sales Invoice",
                {"custom_offline_invoice_number": offline_invoice_number},
                "name",
            )

        if not return_invoice and not offline_no_invoice_id:
            return Response(
                json.dumps({"data": f"Sales Invoice {return_against} not found"}),
                status=404,
                mimetype="application/json",
            )

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
        if pos_profile:
            pos_doc = frappe.get_doc("POS Profile", pos_profile)
            cost_center = pos_doc.cost_center
            source_warehouse = pos_doc.warehouse
            profile_taxes_and_charges = pos_doc.taxes_and_charges
            profile_discount_account = pos_doc.custom_discount_account
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
                "cost_center": item.get("cost_center",cost_center),
                "discount_account": item.get("discount_account", profile_discount_account),
                "allow_zero_valuation_rate": 1
            }
            for item in items
        ]

        payment_items = []
        if payments:
            pos_profile_doc = (
                frappe.get_doc("POS Profile", pos_profile) if pos_profile else None
            )

            for payment in payments:
                mode = payment.get("mode_of_payment", "").strip()
                amount = float(payment.get("amount", 0))

                if mode.lower() in ["cash", "card"] and pos_profile:
                    for row in pos_profile_doc.get("payments") or []:
                        if (
                            row.custom_offline_mode_of_payment1
                            and row.custom_offline_mode_of_payment1.lower() == mode.lower()
                        ):
                            mode = row.mode_of_payment
                            break

                payment_items.append({"mode_of_payment": mode, "amount": amount})

        # if pos_profile:
        #     pos_doc = frappe.get_doc("POS Profile", pos_profile)
        #     cost_center = pos_doc.cost_center
        #     source_warehouse = pos_doc.warehouse
        #     profile_taxes_and_charges = pos_doc.taxes_and_charges

        new_invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "customer": customer_name,
                "custom_unique_id": unique_id,
                "apply_discount_on": "Grand Total",
                "discount_amount": discount_amount,
                "items": invoice_items,
                "payments": payment_items,
                "custom_zatca_pos_name": machine_name,
                "is_pos": 1,
                "is_return": 1,
                "return_against": return_against if return_invoice else offline_no_invoice_id,
                "custom_offline_invoice_number": offline_invoice_number,
                "pos_profile": pos_profile,
                "posa_pos_opening_shift": pos_shift,
                "custom_cashier": cashier,
                "custom_reason": reason,
                "cost_center": cost_center,
                "set_warehouse": source_warehouse,
                "taxes_and_charges": profile_taxes_and_charges,
                "custom_invoice_type": "Retail",
            }
        )

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

        zatca_setting_name = pos_settings.zatca_multiple_setting
        frappe.db.set_value(
            "ZATCA Multiple Setting", zatca_setting_name, "custom_pih", PIH
        )

        doc = frappe.get_doc("ZATCA Multiple Setting", zatca_setting_name)


        item_tax_rate = None

        if new_invoice.items[0].item_tax_template:
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
                    "item_tax_template": item.item_tax_template
                    if item.item_tax_template
                    else None,
                    "allow_zero_valuation_rate": item.allow_zero_valuation_rate,
                    "tax_rate": frappe.get_value(
                        "Item Tax Template Detail",
                        {"parent": item.item_tax_template},
                        "tax_rate",
                    )
                    if item.item_tax_template
                    else None,
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
            filters={"valid_upto": (">=", today),
                     "docstatus":1,
                     "enabled":1},
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
                        "sale_price":float(item.sale_price) if item.sale_price is not None else None,
                        "cost_price":float(item.cost_price)if item.cost_price is not None else None,
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
                        "price_after_discount":float(item.price_after_discount) if item.price_after_discount is not None else None,
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


@frappe.whitelist(allow_guest=True)
def get_valuation_rate(itemcode):
    doc= frappe.db.get_value("Bin",
        {"item_code": itemcode},
        "valuation_rate"
    )
    return doc


@frappe.whitelist()
def create_customer_new(
    customer_name,
    vat_number,
    mobile_no,
    custom_b2c="1",
    pos_profile=None,
    city=None,
    referral_code=None,
    birthday=None,
    customer_group=None,
    territory=None,
    buyer_id_type=None,
    buyer_id=None,
    address_line1=None,
    address_line2=None,
    building_number=None,
    pb_no=None,
):
    try:

        if frappe.db.exists("Customer", {"tax_id": vat_number}):
            return Response(json.dumps({"data": "VAT Number already exists!"}), status=409, mimetype="application/json")
        if frappe.db.exists("Customer", {"mobile_no": mobile_no}):
            return Response(json.dumps({"data": "Mobile Number already exists!"}), status=409, mimetype="application/json")

        if address_line1 and not city:
            frappe.throw(_("City is mandatory when address is provided."))

        pos_profiles = []
        if pos_profile:
            pos_profiles = [{"pos_profile": p} for p in (pos_profile if isinstance(pos_profile, list) else [pos_profile])]


        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "posa_referral_company": frappe.defaults.get_user_default("Company"),
            "tax_id": vat_number,
            "mobile_no": mobile_no,
            "posa_referral_code": referral_code,
            "posa_birthday": birthday,
            "company": frappe.defaults.get_user_default("Company"),
            "custom_pos_profile_table": pos_profiles,
        })

        if customer_group:
            customer.customer_group = customer_group
        if territory:
            customer.territory = territory
        if isinstance(custom_b2c, str):
            custom_b2c = custom_b2c.lower() in ("true", "1", "yes")
            customer.custom_b2c = 1 if custom_b2c else 0
        if buyer_id_type:
            customer.custom_buyer_id_type = buyer_id_type
        if buyer_id:
            customer.custom_buyer_id = buyer_id

        customer.save(ignore_permissions=True)


        address_data = {}
        if address_line1:
            address = frappe.get_doc({
                "doctype": "Address",
                "address_title": customer_name,
                "address_type": "Billing",
                "customer": customer.name,
                "address_line1": address_line1,
                "city": city,
                "links": [{"link_doctype": "Customer", "link_name": customer.name}]
            })
            if address_line2:
                address.address_line2 = address_line2
            if building_number:
                address.custom_building_number = building_number
            if pb_no:
                address.pincode = pb_no

            address.insert(ignore_permissions=True)
            customer.customer_primary_address = address.name
            customer.save(ignore_permissions=True)

            address_data = {
                "address_1": address.address_line1,
                "address_2": address.address_line2,
                "building_no": address.custom_building_number,
                "pb_no": address.pincode
            }


        data = {
            "id": customer.name,
            "customer": customer.customer_name,
            "customer_group": customer.customer_group,
            "mobile": customer.mobile_no,
            "B2C":customer.custom_b2c if custom_b2c else None,
            "buyer_id_type":customer.custom_buyer_id_type if buyer_id_type else None,
            "buyer_id":customer.custom_buyer_id if buyer_id else none,
            "vat_number": customer.tax_id,
            "pos_profiles": (
        customer.custom_pos_profile_table[0].pos_profile
        if customer.custom_pos_profile_table else None
    ),
            **address_data,
        }

        return Response(json.dumps({"data": data}), status=200, mimetype="application/json")

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")


@frappe.whitelist()
def customer_list(id=None, pos_profile=None):
    try:
        filters = {"name": id} if id else {}
        customers = frappe.get_list(
            "Customer",
            fields=[
                "name as id",
                "customer_name",
                "mobile_no",
                "email_id",
                "tax_id",
                "customer_group",
                "territory",
                "customer_primary_address",
                "custom_default_pos",
                "disabled",
                "custom_b2c",
                "custom_buyer_id_type",
                "custom_buyer_id"
            ],
            filters=filters,
        )

        if not customers:
            return Response(
                json.dumps({"error": "Customer not found"}),
                status=404,
                mimetype="application/json",
            )


        if not pos_profile:
            return Response(
                json.dumps({"data": customers}),
                status=200,
                mimetype="application/json",
            )


        if not frappe.db.exists("POS Profile", pos_profile):
            return Response(
                json.dumps({"error": "POS Profile not found"}),
                status=404,
                mimetype="application/json",
            )

        default_customer = frappe.db.get_value("POS Profile", pos_profile, "customer")

        filtered_customers = []
        for cust in customers:
            cust["custom_default_pos"] = 0


            if default_customer and cust["id"] == default_customer:
                pos_profiles = frappe.get_all(
                "pos profile child table",
                filters={"parent": cust["id"], "pos_profile": pos_profile},
                fields=["pos_profile"],
                )
                if pos_profiles:
                    cust["custom_default_pos"] = 1
                    filtered_customers.append(cust)
                    continue


            pos_profiles = frappe.get_all(
                "pos profile child table",
                filters={"parent": cust["id"], "pos_profile": pos_profile},
                fields=["pos_profile"],
            )

            if pos_profiles:
                filtered_customers.append(cust)

        if not filtered_customers:
            return Response(
                json.dumps({"error": "No customers found for given POS Profile"}),
                status=404,
                mimetype="application/json",
            )


        data = []
        for customer in filtered_customers:
            address_data = {}
            if customer.customer_primary_address:
                address = frappe.get_doc("Address", customer.customer_primary_address)
                address_data = {
                    "address_1": address.address_line1,
                    "address_2": address.address_line2,
                    "building_no": int(address.custom_building_number) if address.custom_building_number else None,
                    "pb_no": int(address.pincode) if address.pincode else None
                }

            data.append({
                "id": customer.get("id"),
                "customer_name": customer.get("customer_name"),
                "phone_no": customer.get("mobile_no"),
                "vat_number": customer.get("tax_id"),
                "customer_group": customer.get("customer_group"),
                "custom_default_pos": customer.get("custom_default_pos"),
                "B2C":customer.get("custom_b2c"),
                "buyer_id":customer.get("custom_buyer_id"),
                "buyer_id_type":customer.get("custom_buyer_id_type"),
                "disabled": customer.get("disabled"),
                **address_data,
            })

        return Response(json.dumps({"data": data}), status=200, mimetype="application/json")

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")



@frappe.whitelist()
def cardpay_log(branch=None,unique_id=None, response_json=None, date_time=None, userId=None, status=None):
    try:

        doc = frappe.get_doc({
            "doctype": "Credit Card Machine Log",
            "branch": branch,
            "response_json": response_json,
            "user_id": userId,
            "status": status,
            "unique_id":unique_id,
            "datetim": date_time
        })


        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        data = {
            "id":doc.name,
            "branch":doc.branch,
            "response_json":doc.response_json,
            "user_id":doc.user_id,
            "status":doc.status,
            "datetime":doc.datetim,
            "unique_id":doc.unique_id
        }
        return Response(json.dumps({"data":data}), status=200, mimetype="application/json")

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "CardPay Log Error")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype="application/json")







@frappe.whitelist()
def get_coupon_details(coupon_code):

    if not coupon_code:
        frappe.throw(_("Coupon Code is required"))

    coupon = frappe.db.get_value(
        "Coupon Code",
        {"coupon_code": coupon_code},
        ["name", "pricing_rule", "valid_from", "valid_upto", "maximum_use", "used"],
        as_dict=True,
    )

    if not coupon:
        frappe.throw(_("Invalid Coupon Code"))


    today = frappe.utils.today()
    if coupon.valid_from and today < str(coupon.valid_from):
        frappe.throw(_("Coupon is not yet valid"))
    if coupon.valid_upto and today > str(coupon.valid_upto):
        frappe.throw(_("Coupon has expired"))


    pricing_rule = frappe.get_doc("Pricing Rule", coupon.pricing_rule)

    data = {
        "coupon_name": coupon.name,
        "coupon_code": coupon_code,
        "pricing_rule": pricing_rule.name,
        "discount_type": pricing_rule.rate_or_discount,
        "discount_amount": pricing_rule.discount_amount or 0,
        "discount_percentage": pricing_rule.discount_percentage or 0,
        "currency": pricing_rule.currency,
        "applicable_on": pricing_rule.apply_on,
        "valid_from": str(coupon.valid_from),
        "valid_upto": str(coupon.valid_upto),
        "maximum_use": coupon.maximum_use,
        "used": coupon.used,
    }

    if pricing_rule.apply_on == "Item Group":
        item_groups = [d.item_group for d in pricing_rule.get("item_groups") if d.item_group]
        data["applicable_item_groups"] = item_groups


    if pricing_rule.apply_on == "Item Code":
        items = [d.item_code for d in pricing_rule.get("items") if d.item_code]
        data["applicable_items"] = items

    return Response(json.dumps({"data": data}), status=200, mimetype="application/json")



@frappe.whitelist(allow_guest=True)
def get_loyalty_item(item):

    item_doc = frappe.get_all("Item", fields=["item_group"], filters={"name": item})
    if not item_doc:
        return {"error": "Item not found"}

    item_group = item_doc[0].get("item_group")
    item_group_doc = frappe.get_all(
        "Item Group",
        fields=["custom_loyalty_percentage"],
        filters={"name": item_group}
    )

    if not item_group_doc:
        frappe.log_error(frappe.get_traceback(), "Item Group not found")
        return {"error": "Item Group not found"}

    return item_group_doc[0]




@frappe.whitelist(allow_guest=True)
def get_loyalty_points(customer_number):
    try:

        customer_doc = frappe.get_all(
            "Loyalty Point Entry Gpos",
            filters={"mobile_no": customer_number},
            fields=["custom_customer"],
            limit=1
        )

        customer = customer_doc[0]["custom_customer"] if customer_doc else None


        total_points = frappe.db.sql("""
            SELECT
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS total_loyalty_points
            FROM
                `tabLoyalty Point Entry Gpos`
            WHERE
                mobile_no = %s
                AND used_loyalty_point = '0'
                AND is_expired = 0
        """, (customer_number,), as_dict=True)

        total_loyalty_points = (
            total_points[0]["total_loyalty_points"] if total_points else 0
        )


        data = {
            "customer_id": customer or "",
            "customer_number": customer_number,
            "loyalty_points": total_loyalty_points,
            "Amount":total_loyalty_points,
        }

        return Response(
            json.dumps({"data": data}),
            status=200,
            mimetype="application/json"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Loyalty Points Error")
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            status=500,
            mimetype="application/json"
        )

@frappe.whitelist(allow_guest=True)
def handle_loyalty_points(invoice_name, customer_name, mobile_no):

    try:
        invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)
        loyalty_setting = frappe.get_single("Loyalty Point Setting")

        loyalty_by_group = {}
        calculate_without_tax = loyalty_setting.get("loyalty_calculate_without_tax")


        for item in invoice_doc.items:
            loyalty_info = get_loyalty_item(item.item_code)
            if not loyalty_info or "error" in loyalty_info:
                continue


            loyalty_percentage = float(loyalty_info.get("custom_loyalty_percentage") or 0)


            if (
                loyalty_percentage == 0
                and loyalty_setting.get("loyalty_point_percentage_if_not_defined_in_item_group") == 1
            ):
                loyalty_percentage = loyalty_setting.get("loyalty_percentage")

            item_group = frappe.db.get_value("Item", item.item_code, "item_group")

            if calculate_without_tax == 1 and loyalty_percentage > 0:
                points = (loyalty_percentage / 100) * float(item.amount)
                loyalty_by_group[item_group] = loyalty_by_group.get(item_group, 0) + points

        total_loyalty_points = sum(loyalty_by_group.values())


        redeemed_points = 0
        for pay in invoice_doc.payments:
            if pay.mode_of_payment and pay.mode_of_payment.lower() in ["loyalty", "loyalty point"]:
                redeemed_points = float(pay.amount)
                break


        if total_loyalty_points > 0 or redeemed_points > 0:
            # If no mobile number, DO NOT add loyalty entry
            if not mobile_no:
                return {
                    "status": "success",
                    "earned_points": 0,
                    "redeemed_points": 0,
                    "message": "Loyalty points NOT added because no mobile number was provided."
                }


            loyalty_doc = frappe.get_doc({
                "doctype": "Loyalty Point Entry Gpos",
                "invoice_id": invoice_doc.name,
                "date": invoice_doc.posting_date,
                "total_amount": invoice_doc.grand_total,
                "custom_customer": customer_name,
                "mobile_no": mobile_no,
                "debit": total_loyalty_points if total_loyalty_points > 0 else 0,
                "credit": redeemed_points if redeemed_points > 0 else 0,
                "loyalty_point": total_loyalty_points if total_loyalty_points > 0 else None,
                "redeem_against": invoice_doc.name if redeemed_points > 0 else None,
            })
            loyalty_doc.insert(ignore_permissions=True)




            if redeemed_points > 0 and mobile_no:
                remaining_to_redeem = redeemed_points


                previous_entries = frappe.get_all(
                    "Loyalty Point Entry Gpos",
                    filters={
                        "mobile_no": mobile_no,
                        "used_loyalty_point": ["!=", 1],
                        "credit": 0
                    },
                    fields=["name", "debit"],
                    order_by="creation asc"
                )

                for entry in previous_entries:
                    if remaining_to_redeem <= 0:
                        break

                    entry_doc = frappe.get_doc("Loyalty Point Entry Gpos", entry.name)
                    available_points = float(entry_doc.debit or 0)

                    if available_points <= remaining_to_redeem:
                        remaining_to_redeem -= available_points

        return {
            "status": "success",
            "earned_points": total_loyalty_points,
            "redeemed_points": redeemed_points
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Loyalty Calculation Error")
        return {"status": "error", "message": "Loyalty calculation failed"}



import random

@frappe.whitelist(allow_guest=True)
def generate_otp(mobile_no):
    otp = str(random.randint(100000, 999999))
    key = f"otp:{mobile_no}"
    frappe.cache().set_value(key, otp, expires_in_sec=300)

    data = {"otp": otp}
    send_message(mobile_no,otp)
    return Response(
            json.dumps({"data": data}),
            status=200,
            mimetype="application/json"
        )


@frappe.whitelist(allow_guest=True)
def validate_otp(mobile_no, otp):
    key = f"otp:{mobile_no}"
    stored_otp = frappe.cache().get_value(key)

    if not stored_otp:
        data = {
                "status": "error",
                "message": "OTP expired or not found"
               }
        return Response(
            json.dumps({"data": data}),
            status=404,
            mimetype="application/json"
        )
    if stored_otp != otp:
        data={
            "status": "error",
            "message": "Invalid OTP"
            }
        return Response(
            json.dumps({"data": data}),
            status=404,
            mimetype="application/json"
        )

    frappe.cache().delete_key(key)

    data = {
        "status": "success",
        "message": "OTP verified"
        }
    return Response(
            json.dumps({"data": data}),
            status=200,
            mimetype="application/json"
        )

@frappe.whitelist(allow_guest=True)
def send_message(mobile_no,otp):
        url =frappe.get_doc('Whatsapp Saudi').get('message_url')
        instance =frappe.get_doc('Whatsapp Saudi').get('instance_id')
        token =frappe.get_doc('Whatsapp Saudi').get('token')
        recipients = get_receiver_phone_number(mobile_no)
        for receipt in recipients:
            number = receipt
            frappe.log_error(number)
            phoneNumber = get_receiver_phone_number(mobile_no)
        querystring = {
            "instanceid":instance,
            "token": token,
            "phone":phoneNumber,
            "body": (
                f"رمز التحقق لاستبدال نقاط الولاء في الجواد بريميوم هو *{otp}*.\n"
                "هذا الرمز صالح لمدة 10 دقائق يُرجى مشاركته مع أمين الصندوق للتحقق.\n\n"
                f"The verification code for redeeming your loyalty points in Aljawad Premium is {otp}. "
                "This is valid for 10 min and please share it with the cashier for validation."
            )
        }
        try:
            frappe.log_error("WhatsApp API Payload", f"Query: {frappe.as_json(querystring)}")
            response = requests.get(url, params=querystring)
            response_json=response.text
            if response.status_code == 200:
                response_dict = json.loads(response_json)
                if response_dict.get("sent") and response_dict.get("id"):
                    current_time = now_datetime()
                    # If the message is sent successfully a success message response will be recorded in the WhatsApp Saudi success log."
                    frappe.get_doc({
                        "doctype": "whatsapp saudi success log",
                        "title": "Message successfully sent",
                        "message":otp,
                        "to_number": number,
                        "time": current_time
                    }).insert()

                else:
                    frappe.log_error(ERROR_MESSAGE, frappe.get_traceback())
            else:
                frappe.log_error("status code  is not 200", frappe.get_traceback())
            return response
        except requests.exceptions.RequestException:
            frappe.log_error(title='Failed to send notification', message=frappe.get_traceback())



def get_receiver_phone_number(number):
        phoneNumber = number.replace("+","").replace("-","")
        if phoneNumber.startswith("+") == True:
            phoneNumber = phoneNumber[1:]
        elif phoneNumber.startswith("00") == True:
            phoneNumber = phoneNumber[2:]
        elif phoneNumber.startswith("0") == True:
            if len(phoneNumber) == 10:
                phoneNumber = "966" + phoneNumber[1:]
        else:
            if len(phoneNumber) < 10:
                phoneNumber ="966" + phoneNumber
        if phoneNumber.startswith("0") == True:
            phoneNumber = phoneNumber[1:]

        return phoneNumber




@frappe.whitelist(allow_guest=True)
def expire_loyalty_points():
    today = frappe.utils.today()

    entries = frappe.get_all(
        "Loyalty Point Entry Gpos",
        filters={
            "expiry_date": ("<=", today),
            "is_expired": 0,
        },
        fields=["name"]
    )

    for e in entries:
        doc = frappe.get_doc("Loyalty Point Entry Gpos", e.name)
        doc.is_expired = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()

