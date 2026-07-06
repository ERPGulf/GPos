import frappe
from frappe.utils import nowdate, getdate, add_days
@frappe.whitelist(allow_guest=True)
def get_kpi_summary(from_date=None, to_date=None, pos_profile=None, branch=None):
    """Return headline KPI numbers for the dashboard strip."""
    from_date = from_date or nowdate()
    to_date   = to_date   or nowdate()

    conditions = "AND posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if pos_profile:
        conditions += " AND pos_profile = %(pos_profile)s"

    params = {"from_date": from_date, "to_date": to_date, "pos_profile": pos_profile}

    # Total sales (Paid submitted invoices only)
    sales = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND status = 'Paid'
          {conditions}
    """.format(conditions=conditions), params)[0][0] or 0

    # Transaction count
    txn_count = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND status = 'Paid'
          {conditions}
    """.format(conditions=conditions), params)[0][0] or 0

    # Average basket
    avg_basket = round(float(sales) / int(txn_count), 2) if txn_count else 0

    # Returns (is_return = 1)
    returns = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return = 1
          {conditions}
    """.format(conditions=conditions), params)[0][0] or 0

    # Stock alerts — OOS items sold in the filtered date range
    oos = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBin`
        WHERE actual_qty <= 0 AND item_code IN (
            SELECT DISTINCT item_code FROM `tabSales Invoice Item`
            WHERE parent IN (SELECT name FROM `tabSales Invoice`
                             WHERE posting_date BETWEEN %(from_date)s AND %(to_date)s
                             AND docstatus = 1)
        )
    """, params)[0][0]

    return {
        "sales": float(sales),
        "txn_count": int(txn_count),
        "avg_basket": avg_basket,
        "returns": int(returns),
        "stock_alert_count": oos,
        "currency": frappe.defaults.get_global_default("currency")
    }


@frappe.whitelist(allow_guest=True)
def get_hourly_sales(date=None, pos_profile=None):
    """Return hourly buckets for today and yesterday for the line chart."""
    today = date or nowdate()
    yesterday = add_days(today, -1)

    def _fetch(target_date):
        profile_condition = "AND pos_profile = %(pos_profile)s" if pos_profile else ""
        rows = frappe.db.sql("""
            SELECT
                HOUR(posting_time) AS hour,
                SUM(grand_total)   AS amount
            FROM `tabSales Invoice`
            WHERE posting_date = %(date)s
              AND docstatus = 1
              AND is_pos = 1
              AND (is_return = 0 OR is_return IS NULL)
              {profile_condition}
            GROUP BY HOUR(posting_time)
            ORDER BY hour
        """.format(profile_condition=profile_condition), {
            "date": target_date,
            "pos_profile": pos_profile
        }, as_dict=1)

        bucket = {r.hour: float(r.amount) for r in rows}
        return [bucket.get(h, 0) for h in range(6, 23)]  # 6am–10pm

    return {
        "hours": [f"{h}:00" for h in range(6, 23)],
        "today": _fetch(today),
        "yesterday": _fetch(yesterday)
    }

@frappe.whitelist(allow_guest=True)
def get_top_items(from_date=None, to_date=None, pos_profile=None, limit=10):


    from_date = from_date or nowdate()
    to_date = to_date or nowdate()

    conditions = "AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if pos_profile:
        conditions += " AND si.pos_profile = %(pos_profile)s"

    rows = frappe.db.sql("""
        SELECT
            sii.item_code,
            sii.item_name,
            SUM(sii.qty)        AS qty,
            SUM(sii.amount)     AS revenue
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1
          AND (si.is_return = 0 OR si.is_return IS NULL)
          {conditions}
        GROUP BY sii.item_code, sii.item_name
        ORDER BY revenue DESC
        LIMIT %(limit)s
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile,
        "limit": int(limit)
    }, as_dict=1)

    return rows

@frappe.whitelist(allow_guest=True)
def get_payment_breakdown(from_date=None, to_date=None, pos_profile=None):


    from_date = from_date or nowdate()
    to_date   = to_date   or nowdate()

    conditions = "AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if pos_profile:
        conditions += " AND si.pos_profile = %(pos_profile)s"

    rows = frappe.db.sql("""
        SELECT
            sip.mode_of_payment,
            ppm.custom_offline_mode_of_payment1 AS payment_type,
            SUM(sip.amount) AS amount
        FROM `tabSales Invoice Payment` sip
        INNER JOIN `tabSales Invoice` si ON si.name = sip.parent
        LEFT JOIN `tabPOS Payment Method` ppm
            ON ppm.parent = si.pos_profile
           AND ppm.mode_of_payment = sip.mode_of_payment
        WHERE si.docstatus = 1
          AND (si.is_return = 0 OR si.is_return IS NULL)
          {conditions}
        GROUP BY sip.mode_of_payment, ppm.custom_offline_mode_of_payment1
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    }, as_dict=1)

    result = {
        "cash":    0,
        "card":    0,
        "loyalty": 0,
        "other":   0
    }

    for row in rows:
        payment_type = (row.payment_type or "").lower()
        amount = float(row.amount or 0)
        if payment_type == "cash":
            result["cash"] += amount
        elif payment_type == "card":
            result["card"] += amount
        elif payment_type == "loyalty":
            result["loyalty"] += amount
        else:
            result["other"] += amount

    return result

@frappe.whitelist(allow_guest=True)
def get_cashier_performance(from_date=None, to_date=None, pos_profile=None):


    from_date = from_date or nowdate()
    to_date   = to_date   or nowdate()

    conditions = "AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if pos_profile:
        conditions += " AND si.pos_profile = %(pos_profile)s"

    # Sales per cashier
    rows = frappe.db.sql("""
        SELECT
            si.owner                        AS cashier,
            si.pos_profile                  AS terminal,
            COUNT(si.name)                  AS txns,
            SUM(si.grand_total)             AS sales,
            SUM(CASE WHEN si.is_return = 1 THEN 1 ELSE 0 END) AS voids
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          {conditions}
        GROUP BY si.owner, si.pos_profile
        ORDER BY sales DESC
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    }, as_dict=1)

    # Get active POS opening entries to determine shift status
    active_sessions = frappe.db.sql("""
        SELECT user, pos_profile, status
        FROM `tabPOS Opening Entry`
        WHERE docstatus = 1
          AND status IN ('Open', 'Closed')
    """, as_dict=1)

    session_map = {
        (s.user, s.pos_profile): s.status for s in active_sessions
    }

    for row in rows:
        status = session_map.get((row.cashier, row.terminal), "Closed")
        row["status"] = status
        row["sales"]  = float(row.sales or 0)

        # Get full name instead of user id
        full_name = frappe.db.get_value("User", row.cashier, "full_name")
        row["cashier"] = full_name or row.cashier

    return rows


@frappe.whitelist(allow_guest=True)
def get_stock_alerts(warehouse=None):


    warehouse_condition = ""
    if warehouse:
        warehouse_condition = "AND b.warehouse = %(warehouse)s"

    # Out of Stock items (sold today but qty <= 0)
    oos_items = frappe.db.sql("""
        SELECT
            i.item_code,
            i.item_name,
            COALESCE(b.actual_qty, 0) AS qty,
            b.warehouse
        FROM `tabItem` i
        LEFT JOIN `tabBin` b ON b.item_code = i.item_code
        WHERE i.disabled = 0
          AND COALESCE(b.actual_qty, 0) <= 0
          AND i.item_code IN (
              SELECT DISTINCT sii.item_code
              FROM `tabSales Invoice Item` sii
              INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
              WHERE si.docstatus = 1
                AND si.posting_date = %(today)s
          )
          {warehouse_condition}
    """.format(warehouse_condition=warehouse_condition), {
        "today": nowdate(),
        "warehouse": warehouse
    }, as_dict=1)

    # Low stock items (qty > 0 but below reorder level)
    low_stock_items = frappe.db.sql("""
        SELECT
            i.item_code,
            i.item_name,
            COALESCE(b.actual_qty, 0) AS qty,
            b.warehouse,
            wr.warehouse_reorder_level  AS reorder_level
        FROM `tabItem` i
        INNER JOIN `tabBin` b ON b.item_code = i.item_code
        LEFT JOIN `tabItem Reorder` wr ON wr.parent = i.item_code
        WHERE i.disabled = 0
          AND COALESCE(b.actual_qty, 0) > 0
          AND COALESCE(b.actual_qty, 0) <= COALESCE(wr.warehouse_reorder_level, 10)
          {warehouse_condition}
        ORDER BY b.actual_qty ASC
        LIMIT 20
    """.format(warehouse_condition=warehouse_condition), {
        "warehouse": warehouse
    }, as_dict=1)

    # Expiring items (batch expiry within next 7 days)
    expiring_items = frappe.db.sql("""
        SELECT
            b.item,
            i.item_name,
            SUM(b.batch_qty) AS qty,
            b.batch_id,
            b.expiry_date
        FROM `tabBatch` b
        INNER JOIN `tabItem` i ON i.item_code = b.item
        WHERE b.expiry_date BETWEEN %(today)s AND %(expiry_limit)s
          AND b.batch_qty > 0
          AND b.disabled = 0
        GROUP BY b.item, b.batch_id, b.expiry_date
        ORDER BY b.expiry_date ASC
        LIMIT 20
    """, {
        "today": nowdate(),
        "expiry_limit": add_days(nowdate(), 7)
    }, as_dict=1)

    alerts = []

    for item in oos_items:
        alerts.append({
            "type": "Out of Stock",
            "item": item.item_name,
            "item_code": item.item_code,
            "qty": item.qty,
            "note": f"Warehouse: {item.warehouse or 'N/A'}"
        })

    for item in low_stock_items:
        alerts.append({
            "type": "Low Stock",
            "item": item.item_name,
            "item_code": item.item_code,
            "qty": item.qty,
            "note": f"Reorder level: {item.reorder_level or 10} | Warehouse: {item.warehouse or 'N/A'}"
        })

    for item in expiring_items:
        days_left = (getdate(item.expiry_date) - getdate(nowdate())).days
        alerts.append({
            "type": "Expiring Soon",
            "item": item.item_name,
            "item_code": item.item,
            "qty": item.qty,
            "note": f"Batch: {item.batch_id} | Expires in {days_left} day(s)"
        })

    return alerts


@frappe.whitelist(allow_guest=True)
def get_transaction_heatmap(pos_profile=None):

    conditions = ""
    if pos_profile:
        conditions = "AND pos_profile = %(pos_profile)s"

    rows = frappe.db.sql("""
        SELECT
            DAYNAME(posting_date)           AS day_name,
            DAYOFWEEK(posting_date)         AS day_num,
            HOUR(posting_time)              AS hour,
            COUNT(name)                     AS txn_count
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND (is_return = 0 OR is_return IS NULL)
          AND posting_date BETWEEN %(from_date)s AND %(to_date)s
          {conditions}
        GROUP BY day_num, day_name, hour
        ORDER BY day_num, hour
    """.format(conditions=conditions), {
        "from_date": add_days(nowdate(), -6),
        "to_date": nowdate(),
        "pos_profile": pos_profile
    }, as_dict=1)

    # Build 7 days x 16 hours matrix (6am to 10pm)
    days = []
    for i in range(6, -1, -1):
        days.append(add_days(nowdate(), -i))

    hours = list(range(6, 22))  # 6am to 9pm

    # Initialize matrix with zeros
    matrix = {}
    for day in days:
        matrix[day] = {h: 0 for h in hours}

    # Fill matrix with actual data
    for row in rows:
        day_key = add_days(nowdate(), -(6 - (int(row.day_num) - 1)))
        if row.hour in hours:
            # match by day_name to avoid off-by-one issues
            for day in days:

                if getdate(day).strftime("%A") == row.day_name:
                    matrix[day][row.hour] = int(row.txn_count)

    # Format for frontend
    result = {
        "days": [getdate(d).strftime("%a %d/%m") for d in days],
        "hours": [f"{h}:00" for h in hours],
        "matrix": [
            [matrix[day][h] for h in hours]
            for day in days
        ]
    }

    return result

@frappe.whitelist(allow_guest=True)
def get_discount_void_summary(from_date=None, to_date=None, pos_profile=None):


    from_date = from_date or nowdate()
    to_date   = to_date   or nowdate()

    conditions = "AND posting_date BETWEEN %(from_date)s AND %(to_date)s"
    if pos_profile:
        conditions += " AND pos_profile = %(pos_profile)s"

    # Total discounts given
    discounts = frappe.db.sql("""
        SELECT COALESCE(SUM(discount_amount), 0) AS total
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND (is_return = 0 OR is_return IS NULL)
          {conditions}
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    })[0][0]

    # Void transactions (is_return = 1)
    voids = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND is_return = 1
          {conditions}
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    })[0][0]

    # Manual price overrides (items where rate != standard rate)
    overrides = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1
          AND sii.discount_percentage > 0
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, {
        "from_date": from_date,
        "to_date": to_date
    })[0][0]

    # Cancelled invoices (no-sales equivalent)
    no_sales = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabSales Invoice`
        WHERE docstatus = 2
          {conditions}
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    })[0][0]

    # Supervisor approvals (amendments)
    approvals = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND amended_from IS NOT NULL
          {conditions}
    """.format(conditions=conditions), {
        "from_date": from_date,
        "to_date": to_date,
        "pos_profile": pos_profile
    })[0][0]

    return {
        "discounts": float(discounts or 0),
        "voids":     int(voids or 0),
        "overrides": int(overrides or 0),
        "no_sales":  int(no_sales or 0),
        "approvals": int(approvals or 0)
    }

@frappe.whitelist(allow_guest=True)
def get_slow_movers(days=7, warehouse=None, limit=20):


    warehouse_condition = ""
    if warehouse:
        warehouse_condition = "WHERE b.warehouse = %(warehouse)s"

    # Items that have stock (in the given warehouse, or across all warehouses
    # when none is specified) but zero sales in the last N days
    rows = frappe.db.sql("""
        SELECT
            i.item_code,
            i.item_name,
            i.item_group,
            COALESCE(stock.total_qty, 0)    AS current_stock,
            sales.last_sale_date            AS last_sale_date
        FROM `tabItem` i
        LEFT JOIN (
            SELECT b.item_code, SUM(b.actual_qty) AS total_qty
            FROM `tabBin` b
            {warehouse_condition}
            GROUP BY b.item_code
        ) stock ON stock.item_code = i.item_code
        LEFT JOIN (
            SELECT sii.item_code,
                   MAX(si.posting_date) AS last_sale_date,
                   SUM(sii.qty)         AS total_sold
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
                AND si.docstatus = 1
                AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
                AND (si.is_return = 0 OR si.is_return IS NULL)
            GROUP BY sii.item_code
        ) sales ON sales.item_code = i.item_code
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
          AND COALESCE(stock.total_qty, 0) > 0
          AND COALESCE(sales.total_sold, 0) = 0
        ORDER BY current_stock DESC
        LIMIT %(limit)s
    """.format(warehouse_condition=warehouse_condition), {
        "from_date": add_days(nowdate(), -int(days)),
        "to_date":   nowdate(),
        "warehouse": warehouse,
        "limit":     int(limit)
    }, as_dict=1)

    for row in rows:
        if row.last_sale_date:
            days_since = (getdate(nowdate()) - getdate(row.last_sale_date)).days
            row["days_since_last_sale"] = days_since
        else:
            row["days_since_last_sale"] = None
            row["last_sale_date"] = "Never"

    return rows

@frappe.whitelist(allow_guest=True)
def get_margin_trend(days=30, pos_profile=None):


    conditions = ""
    if pos_profile:
        conditions = "AND si.pos_profile = %(pos_profile)s"

    rows = frappe.db.sql("""
        SELECT
            si.posting_date                             AS date,
            SUM(si.grand_total)                         AS revenue,
            SUM(si.grand_total - si.net_total)          AS tax_amount,
            SUM(si.net_total)                           AS net_revenue,
            SUM(
                sii.qty * COALESCE(sii.incoming_rate, 0)
            )                                           AS cost
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.docstatus = 1
          AND (si.is_return = 0 OR si.is_return IS NULL)
          AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
          {conditions}
        GROUP BY si.posting_date
        ORDER BY si.posting_date ASC
    """.format(conditions=conditions), {
        "from_date": add_days(nowdate(), -int(days)),
        "to_date":   nowdate(),
        "pos_profile": pos_profile
    }, as_dict=1)

    result = []
    for row in rows:
        revenue = float(row.net_revenue or 0)
        cost    = float(row.cost or 0)

        if revenue > 0:
            gross_profit = revenue - cost
            margin_pct   = round((gross_profit / revenue) * 100, 2)
        else:
            margin_pct = 0

        result.append({
            "date":        str(row.date),
            "revenue":     round(float(row.revenue or 0), 2),
            "cost":        round(cost, 2),
            "margin_pct":  margin_pct
        })

    return result