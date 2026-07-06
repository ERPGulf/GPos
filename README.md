# GPOS

**Gulf POS (GPOS)** is an offline-capable Point of Sale (POS) system for ERPNext, designed to work seamlessly on **Windows**.

##  Version

**Current Version:** `v2.1.1`

##  Features

- Offline billing with local database sync
- Fast UI optimized for retail workflows
- Automatic sync with ERPNext when connection is restored
- Works with ERPNext v15
- Support for multi-user and multi-terminal setups
- Hardware integration: Barcode scanner, printers

##  What's New in v2.1.1

- **Add POS Profiles to Offline Users List**  
  Updated `gpos.gpos.pos.getOfflinePOSUsers` to include POS Profiles for better control and filtering of offline users.

-  **Changed System User to Offline User in Shift Opening**  
  In `gpos.gpos.pos_shift.opening_shift`, system user logic now uses the offline user, improving shift audit consistency.

-  **Datetime Format Standardization**  
  Both `opening_shift` and `closing_shift` now use the datetime format: `YYYY-MM-DD HH:mm:ss` for improved compatibility and logging.

##  Installation

```bash
# Navigate to your bench directory
cd /opt/frappe-bench

# Get the app (use correct repo and branch)
bench get-app gpos https://github.com/ERPGulf/GPos.git --branch v2.1.1

# Install the app on your site
bench --site your-site-name install-app gpos
```

##  Core API (`pos.py` & `pos_shift.py`)

The `gpos/gpos/pos.py` and `gpos/gpos/pos_shift.py` modules expose the whitelisted (REST-callable) API endpoints that power the GPOS point-of-sale application: authentication, item catalog sync, invoicing, customers, loyalty points, coupons, promotions, ZATCA/e-invoicing settings, SMS/OTP, and shift (till) management.

All endpoints are registered with `@frappe.whitelist(...)` and are callable via Frappe's REST API at:

```
/api/method/gpos.gpos.pos.<function_name>
/api/method/gpos.gpos.pos_shift.<function_name>
```

Endpoints marked `allow_guest=True` do not require a logged-in session (they typically do their own token/credential validation). Endpoints without `allow_guest=True` require a valid Frappe session/OAuth token.

### `pos.py`

#### Authentication & Tokens

| Function | Auth | Description |
|---|---|---|
| `generate_token_secure(api_key, api_secret, app_key)` | Guest | Exchanges API key/secret for an OAuth password-grant token. `app_key` is base64-encoded and mapped to an `OAuth Client` record to look up `client_id`/`client_secret`, then proxies a token request to Frappe's own OAuth2 `get_token` endpoint. |
| `generate_token_for_offline_user(api_key, api_secret, app_key)` | Guest | Same flow as `generate_token_secure`, used for offline POS users. |
| `generate_token_secure_for_users(username, password, app_key)` | Logged-in | Username/password login variant of the above; also logs the login attempt and returns basic user info (`User` record) and the branch from `Claudion POS setting`. |
| `create_refresh_token(refresh_token)` | Guest | Exchanges a refresh token for a new access token via Frappe's OAuth2 endpoint. |

#### Item Catalog

| Function | Auth | Description |
|---|---|---|
| `get_items(item_group=None, last_updated_time=None, pos_profile=None)` | Guest | Returns items grouped by item group, with prices (from the POS Profile's selling price list), UOMs, barcodes, and Arabic/English name variants. If `last_updated_time` is given, only returns items/prices modified since then (delta sync). If `pos_profile` is given, restricts to that profile's item groups and price list. |
| `get_items_page(item_group=None, last_updated_time=None, limit=50, offset=0)` | Guest | Paginated variant of `get_items` (no POS profile filtering, no disabled/item-group-disabled logic). |
| `get_valuation_rate(itemcode)` | Guest | Quick lookup of an item's valuation rate from the `Bin` doctype. Returns the raw value (or `None`), not wrapped in `Response`. |
| `get_loyalty_item(item)` | Guest | Given an item, returns its Item Group's `custom_loyalty_percentage`. Returns `{"error": ...}` if the item/item group isn't found; otherwise a plain (non-`Response`-wrapped) value. |

#### Customers

| Function | Auth | Description |
|---|---|---|
| `create_customer(customer_name, lead_name, pos_profile=None, email_id=None, gender=None, mobile_no=None)` | Guest | Creates a `Customer`, or updates an existing one if a matching `Lead` is found by `lead_name`. |
| `create_customer_new(customer_name, vat_number, mobile_no, custom_b2c="1", pos_profile=None, city=None, referral_code=None, birthday=None, customer_group=None, territory=None, buyer_id_type=None, buyer_id=None, address_line1=None, address_line2=None, building_number=None, pb_no=None)` | Logged-in | Current customer creation endpoint. Creates a `Customer` with optional linked `Address` and POS Profile associations, enforcing uniqueness of VAT number and mobile number. Returns 409 if either already exists. |
| `customer_list_old(id=None, pos_profile=None)` | Guest | **Deprecated** — use `customer_list` instead. Lists customers, optionally filtered by name and restricted to those assigned to a POS Profile. |
| `customer_list(id=None, pos_profile=None)` | Logged-in | Current customer listing endpoint replacing `customer_list_old`. Optionally filters by exact `id` and restricts to customers linked to `pos_profile`, flagging the profile's default customer. Returns 404 if none found. |

#### Invoicing

| Function | Auth | Description |
|---|---|---|
| `create_invoice(customer_name, items, machine_name, ...)` | Logged-in | Core sale endpoint. Validates/locks the offline invoice number (`lock_invoice_numbers`), resolves payment modes (mapping offline mode names to POS Profile modes), validates free-item/promotion-only carts, applies coupon/discount logic, creates either a `POS Invoice` or `Sales Invoice` (per `Claudion POS setting`), handles ZATCA phase-2 XML/QR-code file attachments, submits the invoice, awards loyalty points (`handle_loyalty_points`), and returns full invoice + item + tax details. Guards against duplicate submissions via `custom_unique_id` / `custom_offline_invoice_number`. Errors: `ValidationError` → 400/500 depending on message content (with rollback); any other exception → 500 "Fallback" error (with rollback). |
| `create_invoice_unsynced(date_time, invoice_number, clearing_status, type="Sales INvoice", manually_submitted=None, json_dump=None, api_response=None)` | Guest | Logs an offline invoice that failed to sync/clear as an `Invoice Unsynced` record, for later reconciliation. |
| `create_credit_note(customer_name, items, PIH, machine_name, return_against=None, payments=None, discount_amount=None, unique_id=None, offline_invoice_number=None, offline_creation_time=None, pos_profile=None, pos_shift=None, cashier=None, reason=None)` | Logged-in | Creates and submits a Sales Invoice return (credit note) against an original invoice. Mirrors `create_invoice`'s idempotency pattern (`lock_invoice_numbers`, duplicate checks by offline invoice number/unique id), resolves the original invoice via `return_against` or offline invoice number, maps payment modes, optionally attaches `xml`/`qr_code` uploads, reverses loyalty points (`handle_loyalty_points_for_return`), and updates the ZATCA Multiple Setting's PIH. Returns 404/409 for validation issues, 400/500 for `ValidationError`/`Exception`. |
| `get_invoice_details(invoice_number)` | Logged-in | Fetches full details of an existing `Sales Invoice` by name: header info, items (with tax rate), taxes, payments, offline invoice metadata, and xml/qr_code attachments. 404 if not found. |
| `warehouse_details(id=None)` | Guest | Given a POS/Sales Invoice name (or all invoices), returns per-item warehouse assignment plus the warehouse's contact/address info. |

#### POS Configuration & Hardware

| Function | Auth | Description |
|---|---|---|
| `pos_setting(machine_name, pos_profile=None)` | Guest | Aggregates configuration needed to bootstrap a POS terminal: `Claudion POS setting`, `Scale Settings` (barcode-scale parsing rules), `ZATCA Multiple Setting`/`Company` e-invoicing certificates and keys (base64-encoded), sales taxes, CardPay settings, and branch/address details — keyed off `machine_name` (ZATCA multiple setting) and `pos_profile`. |
| `getOfflinePOSUsers(id=None, offset=0, limit=500)` | Guest | Returns offline POS login accounts (`POS Offline Users`) with decrypted+base64-encoded passwords, their assigned POS Profiles, and resolved print template/format HTML. |
| `add_user_key(user_key, user_name)` | Logged-in | Sets a `user_key` custom field on a `User`. |
| `user_login_details(user, log_in, log_out)` | Guest | Records a login/logout event as a `user login details` document. |

#### Loyalty & Promotions

| Function | Auth | Description |
|---|---|---|
| `get_loyalty_points(customer_number)` | Guest | Computes a customer's available loyalty point balance (sum of debits minus credits from `Loyalty Point Entry Gpos`, excluding used/expired points), floored at zero. |
| `expire_loyalty_points()` | Guest | Batch/cron job endpoint — marks all `Loyalty Point Entry Gpos` records past their `expiry_date` as expired (`is_expired = 1`). No response body; intended to be scheduler-triggered, not client-called. |
| `get_promotion_list(pos_profile)` | Guest | Returns active promotions linked to a POS Profile, each with an `items` array (sale/cost price, discount type/percentage/amount, price after discount, `is_free` flag, uom). Used by `create_invoice` to validate free-item-only carts. 404 if the profile isn't linked to any promotion. |
| `get_coupon_details(coupon_code, branch)` | Logged-in | Validates a coupon for a branch (existence, branch eligibility, validity window) and returns its linked Pricing Rule discount info plus applicable item groups/items. Returns 404 (invalid code), 403 (not valid for branch), 400 (not yet valid), or 410 (expired) as appropriate. |
| `claim_coupon(coupon_code, user_branch, uuid)` | Logged-in | Atomically claims/redeems one coupon use for a branch. Uses cache-based idempotency keyed by `uuid` plus cached usage counters to avoid double-claims under concurrent requests, then persists the incremented `used` count. Returns 200 with `claimed:0` if already claimed (idempotent) or `claimed:1` if newly claimed; 400 if branch invalid or usage limit reached. |
| `get_coupons_by_branch(branch)` | Logged-in | Lists all currently valid, non-exhausted coupons for a branch with discount/pricing rule details. 400 if `branch` missing. |

#### Payments

| Function | Auth | Description |
|---|---|---|
| `wallet_refund_request(user, amount, transaction_id=None)` | Guest | Creates a `wallet refund` request record. |
| `cardpay_log(branch=None, unique_id=None, response_json=None, date_time=None, userId=None, status=None)` | Logged-in | Records a card-payment terminal transaction log (`Credit Card Machine Log` doctype) for auditing/reconciliation. Returns the created log's fields, or 500 on exception. |

#### OTP / SMS

| Function | Auth | Description |
|---|---|---|
| `generate_otp(mobile_no)` | Guest | Generates a 6-digit OTP for loyalty-point redemption, caches it (5 min TTL) keyed by mobile number, and sends it via SMS (`send_test_sms`, bilingual Arabic/English message). Returns `{"otp": otp}` — note the OTP is also returned in the response, not just sent by SMS. |
| `validate_otp(mobile_no, otp)` | Guest | Validates a previously generated OTP against the cached value and deletes it on success. Returns 404 if expired/not found/mismatched, 200 on match. |
| `generate_sms_otp(mobile_no)` | Guest | Similar to `generate_otp` but with an English-only message; also returns the SMS gateway's `status_code`/`response`. 500 on exception. |
| `send_test_sms(phone, message)` | Guest | Sends an SMS via a third-party HTTP gateway configured in `Claudion POS setting` (app key/secret, URL, sender, number ISO), logging success/failure to `whatsapp saudi success log` or `frappe.log_error`. Returns `{"status_code": ..., "response": ...}`. |
| `send_message(mobile_no, otp)` | Guest | Sends a WhatsApp OTP message via a "Whatsapp Saudi" gateway, normalizing the phone number first. Returns the raw `requests` response object. **Note:** contains a bug where `phoneNumber` is only defined inside the `for receipt in recipients` loop. |
| `get_receiver_phone_number(number)` | n/a (internal) | Not whitelisted — internal helper called by `send_message`; normalizes a raw phone number into international format (strips `+`/`-`/leading zeros, prefixes Saudi country code `966` when needed). |

#### Shift Status & Sync Logging

| Function | Auth | Description |
|---|---|---|
| `get_shift_status(shift_id)` | Guest | Looks up a `POS Opening Shift`/`POS Closing Shift` by id and returns its status. 400 if `shift_id` missing, 404 if not found in either doctype. |
| `sync_gpos_log(details, datetime, location, sync_id)` | Guest | Writes a debug/sync log entry (`gpos logs` doctype) from the offline client, gated by a global debug-logging setting; `details` is scanned for a "Resource:" line to detect credit-note syncs. Returns 400 if logging disabled, 409 if `sync_id` already logged, 200 on success. |
| `get_pos_offers()` | Logged-in | Returns all currently valid (non-cancelled, non-disabled, within date range) `POS Offer` records — title, discount type/amount/percentage, item, thresholds, applicable warehouse/pos_profile/company, validity, auto-apply flag. Returned as a raw list, not `Response`-wrapped. |

#### File Uploads (generic Frappe helpers)

| Function | Auth | Description |
|---|---|---|
| `upload_file()` | Logged-in | Standard Frappe multi-file upload endpoint; validates permissions, optionally optimizes images, and attaches files to a doctype/field. |
| `optimize_image_content(content, content_type)` | Logged-in | Resizes/optimizes image bytes using Frappe's `optimize_image` utility. |
| `process_file_upload(file, ignore_permissions, is_private=False)` | Logged-in | Reads an uploaded file stream, optionally optimizes it, and creates a `File` document. |
| `attach_field_to_doc(doc)` | Logged-in | Sets the uploaded file's URL onto a target document's field. |
| `validate_user_permissions()` | Logged-in | Checks whether the current session (or guest, if allowed) may upload files. |
| `get_number_of_files(file_storage)` | Logged-in | Returns the number of files in a file storage object, if supported. |
| `parse_json_field(field)` | Guest | Shared helper — parses a JSON string form field into a Python object (also duplicated in `pos_shift.py`). |

#### Debug / Misc

| Function | Auth | Description |
|---|---|---|
| `cache1()` / `cache2()` | Guest | Trivial cache set/get test endpoints — not for production use. |

### `pos_shift.py`

Handles opening and closing a POS terminal's cash/till shift (`POS Opening Shift` / `POS Closing Shift`), analogous to a cash drawer session.

| Function | Auth | Description |
|---|---|---|
| `opening_shift(period_start_date, company, user, pos_profile, name)` | Guest | Opens a new shift. Expects a `balance_details` form field (JSON list of `{mode_of_payment, opening_amount}`), maps offline payment mode names to the POS Profile's configured modes, resolves an offline username to its linked `User` if needed, then creates and submits a `POS Opening Shift` document. Returns the shift's sync id and opening balances. |
| `closing_shift(pos_opening_entry, company=None, period_end_date=None, created_invoice_status=None, name=None, details=None)` | Guest | Closes a shift. Expects `payment_reconciliation` (JSON list of `{mode_of_payment, opening_amount, expected_amount, closing_amount}`) and optional `details` (invoice/return/cash/bank totals). If the referenced opening shift is already closed, returns the existing `POS Closing Shift` instead of creating a duplicate. Otherwise creates and submits a new `POS Closing Shift`, dropping any `loyalty` payment rows. |
| `get_pos_profiles_with_users()` | Guest | Returns every `POS Profile` along with the list of users it's applicable to. |
| `format_datetime_safe(value)` | n/a (internal) | Helper that normalizes a `datetime`/`date`/date-string into a `"%Y-%m-%d %H:%M:%S"` string for JSON responses. |
| `build_closing_shift_response(doc)` | n/a (internal) | Helper that shapes a `POS Closing Shift` document into the JSON response format used by `closing_shift`. |
| `parse_json_field(field)` | Guest | Shared helper — parses a JSON string form field into a Python object. |

#### Notes / Gotchas

- Both `opening_shift` and `closing_shift` re-read several parameters from `frappe.form_dict` rather than trusting the typed function arguments directly (e.g. `name`, `balance_details`, `payment_reconciliation`) — a pattern also used throughout `pos.py`'s `create_invoice`.
- `closing_shift` treats `loyalty` as a payment mode to be excluded from cash/bank reconciliation.
- Errors are logged via `frappe.log_error` and returned as JSON with 4xx/5xx status codes rather than raising, so API clients must check the HTTP status/`error` field rather than relying on exceptions.
