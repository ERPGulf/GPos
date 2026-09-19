frappe.listview_settings["gpos logs"] = {
	onload(listview) {
		listview.page.add_inner_button("Clear Old Logs", function () {
			frappe.confirm(
				"This will permanently delete all gpos logs older than 10 days. Continue?",
				function () {
					frappe.call({
						method: "gpos.gpos.doctype.gpos_logs.gpos_logs.delete_old_gpos_logs",
						freeze: true,
						freeze_message: "Deleting old logs...",
						callback: function (r) {
							frappe.msgprint(r.message);
							listview.refresh();
						}
					});
				}
			);
		});
	}
};
