frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.add_custom_button(__('Apply Discount'), function () {

            if (!frm.doc.items || !frm.doc.items.length) {
                frappe.msgprint(__('No items found'));
                return;
            }

            frappe.call({
                method: 'gpos.gpos.calling_functions.apply_promotion_discount_before_save',
                args: {
                    items: frm.doc.items,
                    cost_center: frm.doc.cost_center,
                    company: frm.doc.company,
                    price_list: frm.doc.selling_price_list
                },
                callback(r) {
                    if (!r.message || r.message.status !== 'success') {
                        frappe.msgprint(__('No applicable promotions'));
                        return;
                    }

                    r.message.items.forEach(promo_item => {
                        let row = frm.doc.items.find(i => i.name === promo_item.name);
                        if (row) {
                            row.rate = promo_item.rate;
                            row.custom_promotion_applied = 1;
                        }
                    });

                    frm.refresh_field('items');
                    frappe.show_alert({
                        message: __('Discount applied successfully'),
                        indicator: 'green'
                    });
                }
            });

        });
    }
});
