frappe.ui.form.on('Item child table', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];


        if (row.item_code) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Item",
                    name: row.item_code
                },
                callback: function(response) {
                    if (response.message) {
                        let item = response.message;
                        let uoms = item.uoms || [];
                        let uom_names = uoms.map(u => u.uom);


                        frappe.model.set_value(cdt, cdn, "uom", "");


                        if (frm.fields_dict.item_table && frm.fields_dict.item_table.grid) {
                            frm.fields_dict.item_table.grid.update_docfield_property(
                                'uom',
                                'options',
                                uom_names.join("\n")
                            );
                        }

                        if (uom_names.length > 0) {
                            frappe.model.set_value(cdt, cdn, "uom", uom_names[0]);
                        } else {
                            console.warn("No UOMs found to set default.");
                        }
                    } else {
                        console.warn("Item not found for item_code:", row.item_code);
                    }
                }
            });
        } else {
            console.log("No item_code selected.");
        }


        if (row.item_code && frm.doc.custom_price_list) {
            get_item_details(frm, cdt, cdn, row);
        }
    },
    uom: function(frm, cdt, cdn) {
         let row = locals[cdt][cdn];
          if (row.item_code && frm.doc.custom_price_list) {
            get_item_details(frm, cdt, cdn, row);
        }
    },

    discount_type: function(frm, cdt, cdn) {
        call_discount_api(locals[cdt][cdn], cdt, cdn);
    },
    discount_percentage: function(frm, cdt, cdn) {
        call_discount_api(locals[cdt][cdn], cdt, cdn);
    },
    discount__amount: function(frm, cdt, cdn) {
        call_discount_api(locals[cdt][cdn], cdt, cdn);
    }
});

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
 function get_item_details(frm, cdt, cdn, row){
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
        console.log("itemcode:", row.item_code, "uom:", row.uom);
        frappe.call({
            method: "gpos.gpos.doctype.promotion.promotion.get_valuation_rate",
            args: {
                itemcode: row.item_code,
                uom: row.uom
            },
            callback: function(r) {
                if (r.message !== undefined) {
                    frappe.model.set_value(cdt, cdn, "cost_price", r.message);
                }else{
                        frappe.model.set_value(cdt, cdn, "cost_price", 0);
                }
            }
        });
 }