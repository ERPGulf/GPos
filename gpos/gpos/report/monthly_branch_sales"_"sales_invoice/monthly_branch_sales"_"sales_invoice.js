// Copyright (c) 2025, ERPGulf and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Branch Sales" "Sales Invoice"] = {
	"filters": [
		{
			fieldname: "year",
			label: "Year",
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1
		}

	]
};
