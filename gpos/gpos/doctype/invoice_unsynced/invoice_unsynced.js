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
                                frappe.msgprint("Invoice submitted successfully");


                                 frappe.call({
                                    method: "frappe.client.set_value",
                                    args: {
                                        doctype: "Invoice Unsynced",
                                        name: frm.doc.name,
                                        fieldname: {
                                            "custom_manually_submitted": 1,
                                            "clearing_status": 1
                                        }
                                    },
                                    callback: function() {
                                        frm.reload_doc();
                                    }
                                });
                            },
                            error: function(err) {
                            let message = "Failed to submit invoice.";

                            if (err && err.responseJSON && err.responseJSON.message) {
                                message += "<br>" + err.responseJSON.message;
                            } else if (err && err.responseJSON && err.responseJSON._server_messages) {
                                try {
                                    const serverMessages = JSON.parse(err.responseJSON._server_messages);
                                    message += "<br>" + serverMessages.join("<br>");
                                } catch (e) {
                                    message += "<br>Unknown error parsing server messages.";
                                }
                            } else if (err && err.responseText) {
                                message += "<br>" + err.responseText;
                            }
                            frappe.msgprint(message);
                            console.error(err);
                        }

                        });
                    }
                }
            });
        });
    }
});
