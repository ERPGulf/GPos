frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.add_custom_button('Send SMS', () => {
            frappe.call({
                method: 'gpos.gpos.pos.generate_sms_otp',
                args: {
                    mobile_no: frm.doc.contact_mobile,
                },
                callback: function (r) {
                    console.log("FULL RESPONSE:", r);

                    if (r.message && r.message.status_code === 200) {
                        try {
                            let parsed = JSON.parse(r.message.response);
                            let successCount = parsed.messages?.[0]?.success_count || 0;

                            if (successCount > 0) {
                                frappe.msgprint("SMS sent successfully");
                            } else {
                                frappe.msgprint("SMS sending failed");
                            }

                        } catch (e) {
                            console.error("Parse error:", e);
                            frappe.msgprint("SMS sent but parsing failed");
                        }
                    } else {
                        frappe.msgprint("SMS sending failed");
                    }
                },
                error: function (err) {
                    console.error("ERROR:", err);
                    frappe.msgprint("API Call Failed");
                }
            });
        });
    }
});