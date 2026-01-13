frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        frm.add_custom_button("Apply Discount", function () {

            frappe.call({
                method: "gpos.gpos.calling_functions.apply_promotion_discount",
                args: {
                    sales_invoice: frm.doc.name
                },
                freeze: true,
                callback: function (r) {
                    console.log("Server response:", r.message);

                    if (!r.message) {
                        frappe.msgprint("No response from server");
                        return;
                    }

                    if (r.message.status === "success") {
                        frm.reload_doc();
                        frappe.msgprint("Promotion discount applied successfully");
                    } else {
                        frappe.msgprint(r.message.message || "No discount applied");
                    }
                }
            });

        });
    }
});
