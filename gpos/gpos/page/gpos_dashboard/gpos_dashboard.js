frappe.pages['gpos-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'gpos dashboard',
		single_column: true
	});
}