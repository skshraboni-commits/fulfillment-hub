import sqlite3
from datetime import datetime, timedelta
import pandas as pd

DB_FILE = "fulfillment.db"

# Fixed demo clock, so the dashboard looks the same every time it is opened
DEMO_NOW = datetime(2026, 10, 5, 14, 30)

STATUSES = ["Received", "Processed", "Picking", "Packing", "Staged", "Shipped"]


def run_query(sql, params=()):
    """Run a SELECT and return the result as a table (DataFrame)."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def run_update(sql, params=()):
    """Run an INSERT/UPDATE (used later when workers change a status)."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def get_orders():
    df = run_query("SELECT * FROM orders")
    for col in ["created_at", "ship_by", "shipped_at"]:
        df[col] = pd.to_datetime(df[col])
    return df


def get_open_issues():
    return run_query("SELECT * FROM issues WHERE status != 'Resolved'")


def time_left(ship_by):
    """Plain-language time until (or past) the deadline."""
    mins = int((ship_by - DEMO_NOW).total_seconds() // 60)
    if mins < 0:
        m = -mins
        return f"Overdue by {m // 60}h {m % 60}m"
    return f"{mins // 60}h {mins % 60}m left"


def get_kpis(orders, open_issues):
    not_shipped = orders[orders["status"] != "Shipped"]
    shipped = orders[orders["status"] == "Shipped"]

    # Overdue: not shipped, and the ship-by time has passed
    overdue = not_shipped[not_shipped["ship_by"] < DEMO_NOW]

    # Priority at risk: priority, not yet staged, deadline within 2 hours
    at_risk = not_shipped[
        (not_shipped["is_priority"] == 1)
        & (not_shipped["status"] != "Staged")
        & (not_shipped["ship_by"] <= DEMO_NOW + timedelta(hours=2))
    ]

    # Blocked: someone recorded a stock problem on the order
    blocked = not_shipped[not_shipped["blocked_reason"].notna()]

    # Awaiting pickup: packed boxes sitting in staging
    awaiting = orders[orders["status"] == "Staged"]

    # On-time rate: shipped before the deadline / all shipped
    on_time = shipped[shipped["shipped_at"] <= shipped["ship_by"]]
    rate = round(100 * len(on_time) / len(shipped)) if len(shipped) else 0

    return {
        "overdue": len(overdue),
        "at_risk": len(at_risk),
        "blocked": len(blocked),
        "awaiting_pickup": len(awaiting),
        "open_issues": len(open_issues),
        "on_time_rate": rate,
    }


def get_needs_attention(orders, open_issues):
    """One row per order that has a problem, with the reasons in plain words."""
    issue_map = (
        open_issues.groupby("order_id")["issue_type"]
        .apply(lambda s: ", ".join(s))
        .to_dict()
    )
    # Priority orders first, then the earliest deadline
    todo = orders[orders["status"] != "Shipped"].sort_values(
        ["is_priority", "ship_by"], ascending=[False, True]
    )

    rows = []
    for _, o in todo.iterrows():
        reasons = []
        if o["ship_by"] < DEMO_NOW:
            reasons.append("OVERDUE")
        elif (
            o["is_priority"] == 1
            and o["status"] != "Staged"
            and o["ship_by"] <= DEMO_NOW + timedelta(hours=2)
        ):
            reasons.append("PRIORITY AT RISK")
        if pd.notna(o["blocked_reason"]):
            reasons.append("BLOCKED: " + o["blocked_reason"])
        if o["order_id"] in issue_map:
            reasons.append("Issue: " + issue_map[o["order_id"]])

        if reasons:
            rows.append({
                "Order": o["order_id"],
                "Priority": "⭐ PRIORITY" if o["is_priority"] == 1 else "",
                "Status": o["status"],
                "Courier": o["courier"],
                "Time left": time_left(o["ship_by"]),
                "What needs attention": " | ".join(reasons),
            })

    return pd.DataFrame(
        rows,
        columns=["Order", "Priority", "Status", "Courier", "Time left", "What needs attention"],
    )

def get_order_items(order_id):
    """Items in one order, with product names and variants."""
    return run_query(
        """
        SELECT p.product_name AS Product, p.variant AS Variant,
               oi.quantity AS Qty, p.shelf_location AS Shelf
        FROM order_items oi
        JOIN products p ON p.sku = oi.sku
        WHERE oi.order_id = ?
        """,
        (order_id,),
    )


def get_order_issues(order_id):
    return run_query(
        "SELECT issue_type AS Type, description AS Description, "
        "owner AS Owner, status AS Status FROM issues WHERE order_id = ?",
        (order_id,),
    )

def get_order_items_with_lookalikes(order_id):
    """Items in an order, including the look-alike variant to watch out for."""
    return run_query(
        """
        SELECT p.product_name AS name, p.variant AS variant,
               oi.quantity AS qty, p.shelf_location AS shelf,
               lk.variant AS lookalike_variant
        FROM order_items oi
        JOIN products p ON p.sku = oi.sku
        LEFT JOIN products lk ON lk.sku = p.lookalike_sku
        WHERE oi.order_id = ?
        """,
        (order_id,),
    )


def move_order(order_id, new_status, bay=None):
    """Change an order's status (and bay when it is staged)."""
    run_update(
        "UPDATE orders SET status = ?, bay_location = ? WHERE order_id = ?",
        (new_status, bay, order_id),
    )

def ship_courier_orders(courier):
    """Mark all staged orders of one courier as shipped (at the demo time)."""
    run_update(
        "UPDATE orders SET status = 'Shipped', shipped_at = ? "
        "WHERE status = 'Staged' AND courier = ? AND bay_location != 'Not found'",
        (DEMO_NOW.strftime("%Y-%m-%d %H:%M"), courier),
    )

def get_inventory():
    return run_query(
        """
        SELECT i.sku, p.product_name, p.variant, p.shelf_location,
               i.main_qty, i.second_qty, i.last_counted_qty, i.reorder_level
        FROM inventory i
        JOIN products p ON p.sku = i.sku
        ORDER BY p.product_name, p.variant
        """
    )


def transfer_stock(sku):
    """Move second-warehouse stock to the main warehouse and unblock waiting orders."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "UPDATE inventory SET main_qty = main_qty + second_qty, "
        "last_counted_qty = last_counted_qty + second_qty, second_qty = 0 "
        "WHERE sku = ?",
        (sku,),
    )
    conn.execute(
        "UPDATE orders SET blocked_reason = NULL "
        "WHERE blocked_reason LIKE 'Stock in second warehouse%' "
        "AND order_id IN (SELECT order_id FROM order_items WHERE sku = ?)",
        (sku,),
    )
    conn.commit()
    conn.close()


def get_all_issues():
    return run_query(
        "SELECT * FROM issues ORDER BY "
        "CASE status WHEN 'Open' THEN 0 WHEN 'In progress' THEN 1 ELSE 2 END, reported_at"
    )


def update_issue_status(issue_id, status):
    run_update("UPDATE issues SET status = ? WHERE issue_id = ?", (status, issue_id))


def add_issue(order_id, issue_type, description, owner):
    n = int(run_query("SELECT COUNT(*) AS n FROM issues")["n"][0])
    run_update(
        "INSERT INTO issues VALUES (?,?,?,?,?,?,?)",
        ("ISS-" + str(n + 1).zfill(2), order_id, issue_type, description,
         owner, "Open", DEMO_NOW.strftime("%Y-%m-%d %H:%M")),
    )