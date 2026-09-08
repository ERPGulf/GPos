frappe.listview_settings["Invoice Unsynced"] = {
	onload(listview) {
		listview.page.add_inner_button("Update Status", function () {
			frappe.call({
				method: "gpos.gpos.doctype.invoice_unsynced.invoice_unsynced.update_invoice_unsynced_status",
				freeze: true,
				freeze_message: "Checking invoices...",
				callback: function (r) {
					frappe.msgprint(r.message);
					listview.refresh();
				}
			});
		});
	}
};
