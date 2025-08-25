
frappe.ui.form.on("promotion", {
    setup(frm) {

        frm.set_query("uom", "item_table", function (doc, cdt, cdn) {
            const row = locals[cdt][cdn];
            if (!row?.item_code) {
                return {};
            }
            return {
                query: "erpnext.controllers.queries.get_item_uom_query",
                filters: { item_code: row.item_code },
            };
        });
    },
});



frappe.ui.form.on("Item child table", {
    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];

        if (!row) return;


        if (!frm.doc.custom_price_list) {
            frappe.msgprint({
                title: "Missing Price List",
                message: "Please set a Price List before selecting an item.",
                indicator: "red"
            });
        }


        frappe.model.set_value(cdt, cdn, "uom", "");


        get_item_details(frm, cdt, cdn, row);
    },

    uom(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.item_code && frm.doc.custom_price_list) {
            get_item_details(frm, cdt, cdn, row);
        }
    },

    discount_type(frm, cdt, cdn) {
        validate_and_apply_discount(locals[cdt][cdn], cdt, cdn);
    },
    discount_percentage(frm, cdt, cdn) {
        validate_and_apply_discount(locals[cdt][cdn], cdt, cdn);
    },
    discount__amount(frm, cdt, cdn) {
        validate_and_apply_discount(locals[cdt][cdn], cdt, cdn);
    }
});


function validate_and_apply_discount(row, cdt, cdn) {

    if (!row.sale_price || row.sale_price === 0) {
        frappe.msgprint({
            title: "Invalid Discount",
            message: "Cannot apply discount when Sale Price is 0.",
            indicator: "red"
        });
        return;
    }
    call_discount_api(row, cdt, cdn);
}

function call_discount_api(row, cdt, cdn) {
    frappe.call({
        method: "gpos.gpos.doctype.promotion.promotion.calculate_price_after_discount",
        args: {
            sale_price: row.sale_price,
            discount_type: row.discount_type,
            discount_percentage: row.discount_percentage,
            discount__amount: row.discount__amount
        },
        callback: function(r) {
            if (r.message && r.message.price_after_discount !== undefined) {
                frappe.model.set_value(cdt, cdn, "price_after_discount", r.message.price_after_discount);
            }
        }
    });
}

function get_item_details(frm, cdt, cdn, row) {
    frappe.call({
        method: "gpos.gpos.doctype.promotion.promotion.get_item_price",
        args: {
            item_code: row.item_code,
            price_list: frm.doc.custom_price_list,
            uom: row.uom
        },
        callback: function(r) {
            if (r.message && r.message.price !== undefined) {
                frappe.model.set_value(cdt, cdn, "sale_price", r.message.price);
                call_discount_api(row, cdt, cdn);
            }
        }
    });

    frappe.call({
        method: "gpos.gpos.doctype.promotion.promotion.get_valuation_rate",
        args: {
            itemcode: row.item_code,
            uom: row.uom
        },
        callback: function(r) {
            if (r.message !== undefined) {
                frappe.model.set_value(cdt, cdn, "cost_price", r.message);
            } else {
                frappe.model.set_value(cdt, cdn, "cost_price", 0);
            }
        }
    });
}
