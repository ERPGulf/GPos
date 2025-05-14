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
