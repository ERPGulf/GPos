frappe.ui.form.on('Invoice Unsynced', {
    refresh: function (frm) {
        frm.add_custom_button('Submit to Sales Invoice', async function () {
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
                callback: function (r) {
                    if (r.message && r.message.name) {
                        frappe.msgprint("Invoice already exists with this Offline Invoice Number: " + r.message.name);
                    } else {
                        // Create invoice
                        frappe.call({
                            method: "gpos.gpos.pos.create_invoice",
                            args: invoice_data,
                            callback: (res) => {
                                let invoice_id = res.message?.data?.id;

                                if (invoice_id) {
                                    frappe.msgprint(`
                                        <b>Invoice submitted successfully!</b><br>
                                        ID: <a href="/app/sales-invoice/${invoice_id}" target="_blank">${invoice_id}</a>
                                    `);


                                    frappe.call({
                                        method: "frappe.client.set_value",
                                        args: {
                                            doctype: "Invoice Unsynced",
                                            name: frm.doc.name,
                                            fieldname: "custom_manually_submitted",
                                            value: 1
                                        },
                                        callback: function () {
                                            frm.reload_doc();
                                        }
                                    });
                                } else {
                                    frappe.msgprint("Invoice submitted, but ID not returned.");
                                }
                            },
                            error: function (err) {
                                let message = "Failed to submit invoice.";

                                if (err?.responseJSON?.message) {
                                    message += "<br>" + err.responseJSON.message;
                                } else if (err?.responseJSON?._server_messages) {
                                    try {
                                        const serverMessages = JSON.parse(err.responseJSON._server_messages);
                                        message += "<br>" + serverMessages.join("<br>");
                                    } catch (e) {
                                        message += "<br>Unknown error parsing server messages.";
                                    }
                                } else if (err?.responseText) {
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
