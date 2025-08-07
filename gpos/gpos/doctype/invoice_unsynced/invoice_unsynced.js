// Copyright (c) 2025, ERPGulf and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Invoice Unsynced", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Invoice Unsynced', {
    refresh: function(frm) {
        frm.add_custom_button('Submit to Sales Invoice', async function() {
            if (!frm.doc.custom_json_dump) {
                frappe.msgprint("JSON Dump is empty!");
                return;
            }

            let invoice_data;
            try {
                invoice_data = JSON.parse(frm.doc.custom_json_dump);
            } catch (e) {
                frappe.msgprint("Invalid JSON format in JSON Dump.");
                return;
            }

            if (!frm.doc.invoice_number) {
                frappe.msgprint("Offline Invoice Number missing.");
                return;
            }

            // Check if invoice already exists
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Sales Invoice",
                    filters: {
                        custom_offline_invoice_number: frm.doc.invoice_number
                    },
                    fieldname: "name"
                },
                callback: function(r) {
                    if (r.message && r.message.name) {
                        frappe.msgprint("Invoice already exists with this Offline Invoice Number: " + r.message.name);
                    } else {

                        frappe.call({
                            method: "gpos.gpos.pos.create_invoice",
                            args: invoice_data,
                            callback: function(res) {
                                frappe.msgprint("Invoice submitted successfully: " + res.message);
                            },
                            error: function(err) {
                                frappe.msgprint("Failed to submit invoice. Check console for errors.");
                                console.error(err);
                            }
                        });
                    }
                }

            });
        });
    }
});
