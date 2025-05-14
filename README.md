# GPOS

**Gulf POS (GPOS)** is an offline-capable Point  of Sale (POS) system for ERPNext, designed to work seamlessly on **Windows**.

## 🔄 Version

**Current Version:** `v2.1.1`

## 🚀 Features

- Offline billing with local database sync
- Fast UI optimized for retail workflows
- Automatic sync with ERPNext when connection is restored
- Works with ERPNext v15
- Support for multi-user and multi-terminal setups
- Hardware integration: Barcode scanner, printers

## 🧰 Installation

```bash
# Navigate to your bench directory
cd /opt/frappe-bench

# Get the app (replace with actual repo URL)
bench get-app gpos https://github.com/your-org/gpos.git --branch v2.1.1

# Install the app on your site
bench --site your-site-name install-app gpos
