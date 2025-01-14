import requests
import json
import frappe
import json
import urllib.parse;
import base64
from werkzeug.wrappers import Response
from frappe.utils import (
	now_datetime
)

@frappe.whitelist(allow_guest=True)
def generate_token_secure( api_key, api_secret, app_key):


                try:
                    try:
                        app_key = base64.b64decode(app_key).decode("utf-8")
                    except Exception as e:
                        return Response(json.dumps({"message": "Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')
                    clientID, clientSecret, clientUser = frappe.db.get_value('OAuth Client', {'app_name': app_key}, ['client_id', 'client_secret','user'])

                    if clientID is None:
                        # return app_key
                        return Response(json.dumps({"message": "Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')

                    client_id = clientID  # Replace with your OAuth client ID
                    client_secret = clientSecret  # Replace with your OAuth client secret
                    url =  frappe.local.conf.host_name  + "/api/method/frappe.integrations.oauth2.get_token"
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
                        return Response(json.dumps({"data":result_data}), status=200, mimetype='application/json')


                    else:

                        frappe.local.response.http_status_code = 401
                        return json.loads(response.text)


                except Exception as e:


                        return Response(json.dumps({"message": e , "user_count": 0}), status=500, mimetype='application/json')






@frappe.whitelist(allow_guest=True)
def create_refresh_token(refresh_token):
                    url =  frappe.local.conf.host_name  + "/api/method/frappe.integrations.oauth2.get_token"
                    payload = f'grant_type=refresh_token&refresh_token={refresh_token}'
                    headers = {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
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
                                "refresh_token": message_json["refresh_token"]
                            }

                            return  Response(json.dumps({"data": new_message}), status=200, mimetype='application/json')
                        except json.JSONDecodeError as e:
                            return  Response(json.dumps({"data": f"Error decoding JSON: {e}"}), status=401, mimetype='application/json')
                    else:
                        return  Response(json.dumps({"data": response.text}), status=401, mimetype='application/json')



@frappe.whitelist(allow_guest=True)

def get_items(item_group=None):
    fields = ["name","stock_uom", "item_code", "item_name","custom_tax_percentage", "item_group", "description"]
    filters = {"item_group": ['like', f'%{item_group}%']} if item_group else {}
    items = frappe.get_all("Item", fields=fields, filters=filters)

    grouped_items = {}

    for item in items:
        # uom=frappe.get_all("UOM Conversion Detail", filters={"parent": item.name}, fields=["uom","conversion_factor"])
        barcodes = frappe.get_all("Item Barcode", filters={"parent": item.name}, fields=["barcode"])
        item_price = frappe.get_all("Item Price", fields=["price_list_rate"], filters={"item_code": ['like', item.item_code]})

        if item.item_group not in grouped_items:
            grouped_items[item.item_group] = {
                "item_group_id":item.item_group,
                "item_group": item.item_group,
                "items": []
            }

        grouped_items[item.item_group]["items"].append({
            "item_id": item.name,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "tax_percentage":item.custom_tax_percentage,
            "description": item.description,
            "item_price": item_price[0].get("price_list_rate") if item_price else 0.0,
            "barcodes": [{"barcode": barcode.barcode} for barcode in barcodes],
            # "uom":[{"uom":uoms.uom,"conversion_factor":uoms.conversion_factor} for uoms in uom],
            "uom":item.stock_uom
        })

    result = list(grouped_items.values())
    return Response(json.dumps({"data":result}), status=200, mimetype='application/json')


@frappe.whitelist()

def create_invoice(customer_id,items, taxes, Customer_Purchase_Order=None,payments=None,discount_amount=None,unique_id=None):
        if not taxes:
            return Response(json.dumps({"data": "taxes information not provided"}), status=404, mimetype='application/json')

        customer_details = frappe.get_all("Customer", fields=["name"], filters={'name': ['like', customer_id]})
        if not customer_details:
            return Response(json.dumps({"data": "customer id not found"}), status=404, mimetype='application/json')


        try:
            invoice_items = []
            company = frappe.defaults.get_defaults().company
            doc = frappe.get_doc("Company", company)
            payment_items=[]
            for payment in payments:
                mode_of_payment=payment["mode_of_payment"]
                mode_of_payment_exist= frappe.get_value("Mode of Payment", {"name":mode_of_payment}, "name")

                if not mode_of_payment_exist:
                    payment_item={
                        "mode_of_payment":mode_of_payment,
                        "amount":payment.get("amount",0)
                    }
                else:
                    payment_item={
                        "mode_of_payment":mode_of_payment,
                        "amount":payment.get("amount",0)
                    }
                payment_items.append(payment_item)

            # payment_list = [{"mode_of_payment": "Cash"}]

            for item in items:
                item_code = item["item_name"]
                item_exists = frappe.get_value("Item", {"name": item_code}, "name")

                if not item_exists:
                    invoice_item = {
                        "item_name": item_code,
                        "qty": item.get("quantity", 0),
                        "rate": item.get("rate", 0),
                        "uom": item.get("uom", "Nos"),
                        # "income_account": item.get("income_account", income_account)
                    }
                else:
                    invoice_item = {
                        "item_code": item_code,
                        "qty": item.get("quantity", 0),
                        "rate": item.get("rate", 0),
                    }

                invoice_items.append(invoice_item)

            taxes_list = []
            for tax in taxes:
                charge_type = tax.get("charge_type")
                account_head = tax.get("account_head")
                amount = tax.get("amount")
                description=tax.get("description")

                # if charge_type and account_head and amount is not None:
                taxes_list.append({
                        "charge_type": charge_type,
                        "account_head": account_head,
                        "tax_amount": amount,
                        "description": description,

                    })

            new_invoice = frappe.get_doc({
                "doctype": "POS Invoice",
                "customer": customer_id,
                "custom_unique_id":unique_id,
                "discount_amount":discount_amount,
                "items": invoice_items,
                "payments":payment_items,
                "taxes": taxes_list,
                "po_no": Customer_Purchase_Order,


            })

            new_invoice.insert(ignore_permissions=True)
            new_invoice.save()

            iitem = frappe.get_doc("POS Invoice", new_invoice.name)
            payment_dict=[]
            for account in iitem.payments:
                payment_data={
                    "mode_of_payment":account.mode_of_payment,
                    "amount":account.amount
                }
                payment_dict.append(payment_data)
            attribute_dict = []
            for attribute in iitem.items:
                attribute_data = {
                    "item_name": attribute.item_name,
                    "item_code": attribute.item_code,
                    "quantity": attribute.qty,
                    "rate": attribute.rate,
                    "uom": attribute.uom,
                    "income_account": attribute.income_account
                }
                attribute_dict.append(attribute_data)
            sales_dict=[]
            for sales in iitem.taxes:
                sales_data={
                    "charge_type": sales.charge_type,
                    "account_head": sales.account_head,
                    "tax_amount": sales.tax_amount,
                    "total":sales.total,
                    "description": sales.description,
                    # "tax_percentage":sales.tax_percentage

                }
                sales_dict.append(sales_data)
            customer_info = {
                "id": new_invoice.name,
                "customer_id": new_invoice.customer,
                "unique_id":new_invoice.custom_unique_id,
                "customer_name": new_invoice.customer_name,
                "total_quantity": new_invoice.total_qty,
                "total": new_invoice.total,
                "grand_total": new_invoice.grand_total,
                "Customer's Purchase Order": int(new_invoice.po_no),
                "discount_amount":new_invoice.discount_amount,
                "items": attribute_dict,
                "taxes":sales_dict,
                "payments":payment_dict
            }

            return Response(json.dumps({"data": customer_info}), status=200, mimetype='application/json')

        except Exception as e:
                return Response(json.dumps({"message": str(e)}), status=404, mimetype='application/json')





@frappe.whitelist()
def add_user_key(user_key,user_name):
    frappe.db.set_value('User',user_name, {
                "user_key": user_key
            })
    return f"user key:{user_key} added to user name: {user_name}"

@frappe.whitelist(allow_guest=True)
def user_login_details(user,log_in,log_out):
    doc = frappe.get_doc({
        "doctype": "user login details",
        "user":user,
        "log_in":log_in,
        "log_out":log_out,
    })
    doc.insert(ignore_permissions=True)
    return doc


from frappe.exceptions import DoesNotExistError
@frappe.whitelist(allow_guest=True)


def create_customer(customer_name, lead_name, email_id=None, gender=None, mobile_no=None):
    try:
        lead = frappe.get_all('Lead', fields=['lead_name'], filters={'name': ['like', f'{lead_name}']})
        # return customer
        if lead:
            # If customer exists, update the existing customer's fields
            existing_customer=frappe.get_all('Customer', fields=['name'], filters={'lead_name': ['like', f'{lead_name}']})
            existing_customer = frappe.get_doc('Customer', existing_customer[0].name)

            existing_customer.customer_name = customer_name
            existing_customer.email_id = email_id
            existing_customer.gender = gender
            existing_customer.mobile_no = mobile_no
            # Update any other fields as needed
            existing_customer.save(ignore_permissions=True)
            frappe.db.commit()
            return Response(json.dumps({"data": "Customer updated successfully"}), status=200, mimetype='application/json')
        else:
            # If customer doesn't exist, create a new customer
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": customer_name,
                "mobile_no": mobile_no,
                "lead_name": lead_name,
                "email_id": email_id,
                "gender": gender
                # Add more fields as needed
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return Response(json.dumps({"data": "Customer created successfully"}), status=200, mimetype='application/json')
    except DoesNotExistError:
        # Handle DoesNotExistError if needed
        pass



@frappe.whitelist(allow_guest=True)
def customer_list(id=None):
    doc=frappe.get_list('Customer', fields=['name as id','customer_name'],filters={'name': ['like', f'{id}']} if id else None)
    return Response(json.dumps({"data":doc}), status=200, mimetype='application/json')


@frappe.whitelist(allow_guest=True)
def  cache1():
    doc=frappe.cache.set_value("key","testing")
    return doc

@frappe.whitelist(allow_guest=True)
def  cache2():
    doc=cache1()
    doc1=frappe.cache.get_value("key")
    return doc1



@frappe.whitelist(allow_guest=True)
def pos_setting():
    systemSettings = frappe.get_doc('pos setting')
    if systemSettings.show_item==1:
        var=True
    else:
        var=False
    data={

        "discount_field":systemSettings.discount_field,
        "prefix_included_or_not":systemSettings.prefix_included_or_not,
        "no_of_prefix_character":int(systemSettings.no_of_prefix_character),
        "prefix":systemSettings.prefix,
        "item_code_total_digits":int(systemSettings.item_code_total_digits),
        "item_code_starting_position":int(systemSettings.item_code_starting_position),
        "weight_starting_position":int(systemSettings.weight_starting_position),
        "weight_total_digitsexcluding_decimal":int(systemSettings.weight_total_digitsexcluding_decimal),
        "no_of_decimal_in_weights":int(systemSettings.no_of_decimal_in_weights),
        "price_included_in_barcode_or_not":int(systemSettings.price_included_in_barcode_or_not),
        "price_starting_position":int(systemSettings.price_starting_position),
        "price_total_digitsexcluding_decimals":int(systemSettings.price_total_digitsexcluding_decimals),
        "no_of_decimal_in_price":int(systemSettings.no_of_decimal_in_price),
        "show_item_pictures":var

    }
    doc= frappe.get_doc('Company',"Zatca Live (Demo)")
    return doc
    return Response(json.dumps({"data":data}), status=200, mimetype='application/json')


@frappe.whitelist(allow_guest=True)
def warehouse_details(id=None):
    # Define the filter
    filters = {'name': ['like', f'%{id}%']} if id else {}

    # Fetch the list of POS Invoices
        # Fetch all POS Invoices
    pos_invoices = frappe.get_list(
        'POS Invoice',
        fields=['name'],
        filters=filters
    )

    # Initialize list to store all items with warehouse details including POS Invoice name
    all_items_with_warehouse_details = []

    # Iterate over each POS Invoice
    for invoice in pos_invoices:
        # Fetch items for the current invoice
        items = frappe.get_all(
            'POS Invoice Item',
            fields=['item_code', 'warehouse'],
            filters={'parent': invoice['name']}
        )

        # Iterate over items of the current invoice
        for item in items:
            # Check if warehouse is not None before fetching details
            if item['warehouse']:
                try:
                    # Fetch warehouse details
                    warehouse_details = frappe.get_doc('Warehouse', item['warehouse'])
                    # Create dictionary with item, warehouse, and POS Invoice details
                    item_with_details = {
                        'id': invoice['name'],
                        'item_code': item['item_code'],
                        'warehouse': item['warehouse'],
                        'mobile_no': getattr(warehouse_details, 'mobile_no', None),
                        'address_line': getattr(warehouse_details, 'address_line_1', None)
                    }
                    # Append item details to the list
                    all_items_with_warehouse_details.append(item_with_details)
                except frappe.DoesNotExistError:
                    print(f"Warehouse {item['warehouse']} not found")
            else:
                print(f"Item {item['item_code']} does not have a warehouse assigned")

    return Response(json.dumps({"data":all_items_with_warehouse_details}), status=200, mimetype='application/json')

@frappe.whitelist(allow_guest=True)
def wallet_refund_request(user,amount,transaction_id=None):
    wallet_refund = frappe.get_doc({
                "doctype": "wallet refund",
                "user":user,
                "amount":amount,
                "transaction_id":transaction_id,
            })

    wallet_refund.insert(ignore_permissions=True)
    wallet_refund.save()
    doc=frappe.get_all("wallet refund",fields=["user","amount","transaction_id"],filters={'name': ['like', f'{wallet_refund.name}']})
    return Response(json.dumps({"data":doc}), status=200, mimetype='application/json')



@frappe.whitelist(allow_guest=False)
def generate_token_secure_for_users( username, password, app_key):

    # return Response(json.dumps({"message": "2222 Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')
    frappe.log_error(title='Login attempt',message=str(username) + "    " + str(password) + "    " + str(app_key + "  "))
    try:
        try:
            app_key = base64.b64decode(app_key).decode("utf-8")
        except Exception as e:
            return Response(json.dumps({"message": "Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')
        clientID, clientSecret, clientUser = frappe.db.get_value('OAuth Client', {'app_name': app_key}, ['client_id', 'client_secret','user'])

        if clientID is None:
            # return app_key
            return Response(json.dumps({"message": "Security Parameters are not valid" , "user_count": 0}), status=401, mimetype='application/json')

        client_id = clientID  # Replace with your OAuth client ID
        client_secret = clientSecret  # Replace with your OAuth client secret
        url =  frappe.local.conf.host_name  + "/api/method/frappe.integrations.oauth2.get_token"
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
        qid=frappe.get_list("User", fields=["name as id","Full Name","mobile_no as phone","email"], filters={'name': ['like', username]})
        systemSettings = frappe.get_doc('pos setting')
        if response.status_code == 200:

            response_data = json.loads(response.text)

            result = {
                "token": response_data,
                "user": qid[0] if qid else {} ,
                "time":str(now_datetime()),
                "branch_id":systemSettings.branch

            }
            return Response(json.dumps({"data": result}), status=200, mimetype='application/json')
        else:

            frappe.local.response.http_status_code = 401
            return json.loads(response.text)


    except Exception as e:
            # frappe.local.response.http_status_code = 401
            # return json.loads(response.text)
            return Response(json.dumps({"message": e , "user_count": 0}), status=500, mimetype='application/json')




@frappe.whitelist(allow_guest=True)
def getOfflinePOSUsers(id=None,offset=0,limit=50):
    from frappe.utils.password import get_decrypted_password
    import base64
    mypass = get_decrypted_password('POS Offline Users', '3ff95f9d07','password', False)

    docs = frappe.db.get_all('POS Offline Users',
        fields=['name','offine_username','shop_name','password','user as actual_user_name,branch_address', 'printe_template as print_template'],
        # filters=filters,
        order_by='offine_username',
        limit_start=offset,
        limit_page_length=limit)

    for doc in docs:
        doc.password = base64.b64encode(get_decrypted_password("POS Offline Users", doc.name, "password").encode('utf-8')).decode('utf-8')
        # if not client_secret:
        #     continue


    return  Response(json.dumps({"data": docs }), status=200, mimetype='application/json')




