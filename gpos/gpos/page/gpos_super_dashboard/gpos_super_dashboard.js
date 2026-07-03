frappe.pages["gpos-super-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "GPOS Super Dashboard",
		single_column: true
	});

	$(wrapper).find(".layout-main-section")
		.html(frappe.render_template("gpos_super_dashboard", {}));

	// ── State scoped to this page instance ──
	const DashState = {
		from_date: frappe.datetime.nowdate(),
		to_date: frappe.datetime.nowdate(),
		pos_profile: "",
		warehouse: "",
		currency: frappe.boot.sysdefaults.currency || "SAR"
	};

	let hourlyChart = null;
	let paymentDonut = null;
	let marginChart = null;
	let refreshTimer = null;
	let countdown = 60;

	// ── Load all widgets ──
	function load_all_widgets() {
		load_kpi_strip();
		load_hourly_chart();
		load_payment_donut();
		load_top_items();
		load_cashier_table();
		load_stock_alerts();
		load_heatmap();
		load_discount_summary();
		load_slow_movers();
		load_margin_trend();
	}

	// ── Populate POS Profile dropdown ──
	function populate_pos_profiles() {
		frappe.db.get_list("POS Profile", { fields: ["name"], limit: 0 }).then(profiles => {
			const $select = $("#pos-profile");
			profiles.forEach(p => {
				$select.append(`<option value="${p.name}">${p.name}</option>`);
			});
		});
	}

	// ── Populate Warehouse dropdown ──
	function populate_warehouses() {
		frappe.db.get_list("Warehouse", { fields: ["name"], filters: { is_group: 0 }, limit: 0 }).then(warehouses => {
			const $select = $("#warehouse-select");
			warehouses.forEach(w => {
				$select.append(`<option value="${w.name}">${w.name}</option>`);
			});
		});
	}

	// ── Filters ──
	function setup_date_filters() {
		populate_pos_profiles();
		populate_warehouses();

		$("[data-preset]").on("click", function () {
			$("[data-preset]").removeClass("active");
			$(this).addClass("active");

			const preset = $(this).data("preset");
			if (preset === "today") {
				DashState.from_date = frappe.datetime.nowdate();
				DashState.to_date = frappe.datetime.nowdate();
			} else if (preset === "this_week") {
				DashState.from_date = frappe.datetime.week_start();
				DashState.to_date = frappe.datetime.nowdate();
			} else if (preset === "this_month") {
				DashState.from_date = frappe.datetime.month_start();
				DashState.to_date = frappe.datetime.nowdate();
			}
			load_all_widgets();
		});

		$("#apply-filters").on("click", function () {
			DashState.from_date = $("#from-date").val();
			DashState.to_date = $("#to-date").val();
			DashState.pos_profile = $("#pos-profile").val();
			DashState.warehouse = $("#warehouse-select").val();
			load_all_widgets();
		});
	}

	// ── 1. KPI Strip ──
	async function load_kpi_strip() {
		const { message: kpi } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_kpi_summary",
			args: { from_date: DashState.from_date, to_date: DashState.to_date, pos_profile: DashState.pos_profile }
		});
		if (!kpi) return;

		DashState.currency = kpi.currency || DashState.currency;
		const currency = DashState.currency;
		$set_kpi("kpi-sales", currency + " " + fmt_money(kpi.sales));
		$set_kpi("kpi-txns", kpi.txn_count);
		$set_kpi("kpi-basket", currency + " " + (kpi.avg_basket || 0).toFixed(1));
		$set_kpi("kpi-returns", kpi.returns);
		$set_kpi("kpi-alerts", kpi.stock_alert_count, kpi.stock_alert_count > 0 ? "danger" : "success");
	}

	function $set_kpi(id, value, style) {
		const el = document.getElementById(id);
		if (!el) return;
		el.textContent = value;
		if (style === "danger") el.style.color = "#a32d2d";
		if (style === "success") el.style.color = "#3b6d11";
	}

	function fmt_money(n) {
		if (n >= 1000000) return (n / 1000000).toFixed(2) + "M";
		if (n >= 1000) return (n / 1000).toFixed(1) + "K";
		return (n || 0).toFixed(0);
	}

	// ── 2. Hourly Chart ──
	async function load_hourly_chart() {
		const { message: r } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_hourly_sales",
			args: { date: DashState.from_date, pos_profile: DashState.pos_profile }
		});
		if (!r) return;

		const ctx = document.getElementById("hourly-chart");
		if (!ctx) return;
		if (hourlyChart) hourlyChart.destroy();

		hourlyChart = new Chart(ctx, {
			type: "bar",
			data: {
				labels: r.hours,
				datasets: [
					{
						label: "Today",
						data: r.today,
						backgroundColor: "#378add",
						borderRadius: 4,
						order: 2
					},
					{
						label: "Yesterday",
						data: r.yesterday,
						type: "line",
						borderColor: "#b5d4f4",
						borderWidth: 2,
						pointRadius: 0,
						tension: 0.4,
						fill: false,
						order: 1
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: "bottom",
						labels: { font: { size: 12 }, color: "#444", boxWidth: 12, padding: 16 }
					}
				},
				scales: {
					x: {
						ticks: { font: { size: 11 }, color: "#555", maxRotation: 0 },
						grid: { display: false }
					},
					y: {
						beginAtZero: true,
						ticks: {
							font: { size: 11 },
							color: "#555",
							callback: v => DashState.currency + " " + (v >= 1000 ? (v / 1000).toFixed(1) + "K" : v)
						},
						grid: { color: "rgba(0,0,0,0.05)" }
					}
				}
			}
		});
	}

	// ── 3. Payment Donut ──
	async function load_payment_donut() {
		const { message: r } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_payment_breakdown",
			args: { from_date: DashState.from_date, to_date: DashState.to_date, pos_profile: DashState.pos_profile }
		});
		if (!r) return;

		const ctx = document.getElementById("payment-donut");
		if (!ctx) return;
		if (paymentDonut) paymentDonut.destroy();

		paymentDonut = new Chart(ctx, {
			type: "doughnut",
			data: {
				labels: ["Cash", "Card", "Loyalty", "Credit", "Other"],
				datasets: [{
					data: [r.cash, r.card, r.loyalty, r.credit, r.other],
					backgroundColor: ["#378add", "#1d9e75", "#ef9f27", "#d85a30", "#aaaaaa"],
					borderWidth: 2
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: "bottom",
						labels: { font: { size: 12 }, color: "#444", boxWidth: 12, padding: 12 }
					}
				}
			}
		});
	}

	// ── 4. Top Items ──
	async function load_top_items() {
		const { message: items } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_top_items",
			args: { from_date: DashState.from_date, to_date: DashState.to_date, pos_profile: DashState.pos_profile }
		});
		if (!items) return;

		let rows = items.map((item, i) => `
			<tr>
				<td>${i + 1}</td>
				<td>${item.item_name}</td>
				<td>${item.qty}</td>
				<td>${DashState.currency} ${fmt_money(item.revenue)}</td>
			</tr>
		`).join("");

		$("#top-items-body").html(rows);
	}

	// ── 5. Cashier Table ──
	async function load_cashier_table() {
		const { message: rows } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_cashier_performance",
			args: { from_date: DashState.from_date, to_date: DashState.to_date, pos_profile: DashState.pos_profile }
		});
		if (!rows) return;

		let html = rows.map(r => `
			<tr>
				<td>${r.cashier}</td>
				<td>${r.terminal || "-"}</td>
				<td>${r.txns}</td>
				<td>${DashState.currency} ${fmt_money(r.sales)}</td>
				<td>${r.voids}</td>
				<td><span class="badge-status ${r.status === 'Open' ? 'badge-green' : 'badge-gray'}">${r.status}</span></td>
			</tr>
		`).join("");

		$("#cashier-body").html(html);
	}

	// ── 6. Stock Alerts ──
	async function load_stock_alerts() {
		const { message: alerts } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_stock_alerts",
			args: { warehouse: DashState.warehouse }
		});
		if (!alerts) return;

		const colorMap = {
			"Out of Stock": "#a32d2d",
			"Low Stock": "#ba7517",
			"Expiring Soon": "#185fa5"
		};

		let html = alerts.map(a => `
			<div class="alert-item">
				<div class="alert-dot" style="background:${colorMap[a.type] || '#888'}"></div>
				<div><strong>${a.type}</strong><br/>${a.item} · ${a.note}</div>
			</div>
		`).join("");

		$("#stock-alerts-body").html(html || "<p style='color:#888;font-size:13px'>No alerts</p>");
	}

	// ── 7. Heatmap ──
	async function load_heatmap() {
		const { message: r } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_transaction_heatmap",
			args: { pos_profile: DashState.pos_profile }
		});

		if (!r || !r.matrix || !r.matrix.length) {
			$("#heatmap-body").html("<p style='color:#aaa;font-size:13px'>No data</p>");
			return;
		}

		const maxVal = Math.max(...r.matrix.flat(), 1);
		let html = "";

		r.matrix.forEach((dayRow, i) => {
			html += `<div class="hm-row"><span class="hm-day">${r.days[i]}</span>`;
			dayRow.forEach(count => {
				const intensity = (count / maxVal).toFixed(2);
				html += `<div class="hm-cell" style="background:rgba(55,138,221,${intensity})" title="${count} txns"></div>`;
			});
			html += `</div>`;
		});

		html += `<div class="hm-row"><span class="hm-day"></span>`;
		r.hours.forEach(h => {
			html += `<div class="hm-hour">${h}</div>`;
		});
		html += `</div>`;

		$("#heatmap-body").html(html);
	}

	// ── 8. Discount & Void Summary ──
	async function load_discount_summary() {
		const { message: r } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_discount_void_summary",
			args: { from_date: DashState.from_date, to_date: DashState.to_date, pos_profile: DashState.pos_profile }
		});
		if (!r) return;

		$("#disc-discounts").text(DashState.currency + " " + fmt_money(r.discounts));
		$("#disc-voids").text(r.voids);
		$("#disc-overrides").text(r.overrides);
		$("#disc-no-sales").text(r.no_sales);
		$("#disc-approvals").text(r.approvals);
	}

	// ── 9. Slow Movers ──
	async function load_slow_movers() {
		const { message: items } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_slow_movers",
			args: { days: 7, warehouse: DashState.warehouse }
		});
		if (!items) return;

		let html = items.map(item => `
			<tr>
				<td>${item.item_name}</td>
				<td>${item.item_group || "-"}</td>
				<td>${item.current_stock}</td>
				<td>${item.last_sale_date || "Never"}</td>
			</tr>
		`).join("");

		$("#slow-movers-body").html(html);
	}

	// ── 10. Margin Trend ──
	async function load_margin_trend() {
		const { message: trend } = await frappe.call({
			method: "gpos.gpos.page.gpos_super_dashboard.gpos_super_dashboard.get_margin_trend",
			args: { days: 30, pos_profile: DashState.pos_profile }
		});
		if (!trend || !trend.length) return;

		const ctx = document.getElementById("margin-chart");
		if (!ctx) return;
		if (marginChart) marginChart.destroy();

		marginChart = new Chart(ctx, {
			type: "line",
			data: {
				labels: trend.map(r => r.date),
				datasets: [{
					label: "Gross Margin %",
					data: trend.map(r => r.margin_pct),
					borderColor: "#1d9e75",
					backgroundColor: "rgba(29,158,117,0.1)",
					tension: 0.4,
					fill: true,
					pointRadius: 2
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						position: "bottom",
						labels: { font: { size: 12 }, color: "#444", boxWidth: 12, padding: 16 }
					}
				},
				scales: {
					x: {
						ticks: { font: { size: 11 }, color: "#555", maxRotation: 45 },
						grid: { display: false }
					},
					y: {
						beginAtZero: true,
						ticks: {
							font: { size: 11 },
							color: "#555",
							callback: v => v + "%"
						},
						grid: { color: "rgba(0,0,0,0.05)" }
					}
				}
			}
		});
	}

	// ── Auto refresh ──
	function start_auto_refresh(interval_seconds) {
		clearInterval(refreshTimer);
		countdown = interval_seconds;

		refreshTimer = setInterval(() => {
			countdown--;
			$("#refresh-countdown").text(
				countdown > 0 ? `Refreshing in ${countdown}s` : "Refreshing..."
			);
			if (countdown <= 0) {
				countdown = interval_seconds;
				load_all_widgets();
			}
		}, 1000);
	}

	// ── Visibility change: pause/resume refresh when tab hidden ──
	function on_visibility_change() {
		if (document.hidden) {
			clearInterval(refreshTimer);
		} else {
			start_auto_refresh(60);
			load_all_widgets();
		}
	}

	document.addEventListener("visibilitychange", on_visibility_change);

	// ── Cleanup when navigating away from this page ──
	frappe.pages["gpos-super-dashboard"].on_page_hide = function () {
		clearInterval(refreshTimer);
		document.removeEventListener("visibilitychange", on_visibility_change);
	};

	frappe.require("https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js", function () {
		Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";
		Chart.defaults.font.size = 12;
		Chart.defaults.color = "#444";
		Chart.defaults.devicePixelRatio = window.devicePixelRatio || 1;
		setup_date_filters();
		load_all_widgets();
		start_auto_refresh(60);
	});
};
