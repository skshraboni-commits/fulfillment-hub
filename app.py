import os
import subprocess
import sys

import pandas as pd
import streamlit as st
import db

# If the database file does not exist yet (for example on a fresh deployment), create it
if not os.path.exists(db.DB_FILE):
    subprocess.run([sys.executable, "setup_db.py"], check=True)

st.set_page_config(page_title="Fulfillment Hub", page_icon="📦", layout="wide")

# ---------- Sidebar (the menu) ----------
st.sidebar.title("📦 Fulfillment Hub")
page = st.sidebar.radio(
    "Go to", ["Dashboard", "Orders", "Pick & Pack", "Pickups", "Stock & Issues"]
)
st.sidebar.caption(f"Demo time: {db.DEMO_NOW.strftime('%d %b %Y, %H:%M')}")
st.sidebar.divider()
if st.sidebar.button("🔄 Reset demo data"):
    subprocess.run([sys.executable, "setup_db.py"], check=True)
    st.rerun()
st.sidebar.caption("Restores the original sample orders if you have changed things.")


def show_dashboard():
    orders = db.get_orders()
    open_issues = db.get_open_issues()
    k = db.get_kpis(orders, open_issues)

    st.title("Dashboard")
    st.caption("What is happening in the warehouse right now, and what needs attention?")
    with st.expander("New here? What this app does and what to try", expanded=False):
        st.markdown(
            """
**Fulfillment Hub replaces the order spreadsheet with one live view of the warehouse.**
The demo clock is fixed at 5 Oct 2026, 14:30, so the story is the same every time.

| Problem at XYZ | Where to see it solved |
|---|---|
| Can't see order status | **Orders** (search and filters) |
| Delays go unnoticed, priority orders get buried | **Dashboard** (red banner, Needs attention) |
| Stock missing or in the 2nd warehouse | **Stock & Issues** |
| Wrong product or variant shipped | **Pick & Pack** (look-alike warning, tick-to-confirm) |
| Boxes misplaced, courier misses pickup | **Pickups** |
| Problems handled informally | **Stock & Issues** (problem log with owner and status) |

**Try this:** go to Stock & Issues and move the black T-shirt stock, then open Pick & Pack.
Order ORD-1001 is no longer blocked. Use **Reset demo data** in the sidebar at any time.
            """
        )

    # Big, obvious warning banner
    if k["overdue"] or k["at_risk"]:
        st.error(
            f"⚠️ {k['overdue']} orders are overdue and "
            f"{k['at_risk']} priority orders are at risk of missing their deadline."
        )

    # KPI row
    c1, c2, c3 = st.columns(3)
    c1.metric("Overdue orders", k["overdue"])
    c2.metric("Priority at risk", k["at_risk"])
    c3.metric("Blocked by stock", k["blocked"])
    c4, c5, c6 = st.columns(3)
    c4.metric("Boxes awaiting pickup", k["awaiting_pickup"])
    c5.metric("Open issues", k["open_issues"])
    c6.metric("On-time shipment rate", f"{k['on_time_rate']}%")

    # Order pipeline: how many orders are in each stage
    st.subheader("Where are the orders?")
    cols = st.columns(len(db.STATUSES))
    for col, status in zip(cols, db.STATUSES):
        col.metric(status, int((orders["status"] == status).sum()))

    # Needs attention list
    st.subheader("Needs attention")
    attention = db.get_needs_attention(orders, open_issues)
    st.dataframe(attention, hide_index=True)


def show_orders():
    orders = db.get_orders()

    st.title("Orders")
    st.caption("Find any order and see exactly where it is.")

    # Search and filters
    search = st.text_input("Search by order ID or customer name")
    f1, f2, f3 = st.columns(3)
    status_filter = f1.multiselect("Status", db.STATUSES)
    courier_filter = f2.multiselect("Courier", sorted(orders["courier"].unique()))
    priority_only = f3.checkbox("Priority orders only")

    df = orders.copy()
    if search:
        s = search.lower()
        df = df[
            df["order_id"].str.lower().str.contains(s)
            | df["customer_name"].str.lower().str.contains(s)
        ]
    if status_filter:
        df = df[df["status"].isin(status_filter)]
    if courier_filter:
        df = df[df["courier"].isin(courier_filter)]
    if priority_only:
        df = df[df["is_priority"] == 1]

    # Priority first, then earliest deadline
    df = df.copy()
    df["is_done"] = (df["status"] == "Shipped").astype(int)
    df["not_priority"] = 1 - df["is_priority"]
    df = df.sort_values(
        ["is_done", "not_priority", "ship_by", "order_id"]
    ).reset_index(drop=True)

    table = pd.DataFrame({
        "Order": df["order_id"],
        "Priority": df["is_priority"].map({1: "⭐ PRIORITY", 0: ""}),
        "Status": df["status"],
        "Customer": df["customer_name"],
        "City": df["city"],
        "Courier": df["courier"],
        "Deadline": df["ship_by"].dt.strftime("%d %b %H:%M"),
        "Time left": [
            "Shipped" if st_ == "Shipped" else db.time_left(sb)
            for st_, sb in zip(df["status"], df["ship_by"])
        ],
        "Blocked": df["blocked_reason"].fillna(""),
    })

    def colour_row(row):
        if "Overdue" in row["Time left"]:
            return ["background-color: #f8d7da; color: #5c1f1f"] * len(row)
        if row["Priority"]:
            return ["background-color: #fff3cd; color: #5c4a1f"] * len(row)
        return [""] * len(row)

    st.caption(f"Showing {len(table)} of {len(orders)} orders. Open orders first, shipped last. Red = overdue, gold = priority.")
    st.dataframe(table.style.apply(colour_row, axis=1), hide_index=True)

    # Order detail
    st.subheader("Order details")
    if len(df):
        chosen = st.selectbox("Pick an order to see details", df["order_id"])
        o = orders[orders["order_id"] == chosen].iloc[0]
        d1, d2, d3 = st.columns(3)
        d1.metric("Status", o["status"])
        d2.metric("Courier", o["courier"])
        d3.metric("Time left", "Shipped" if o["status"] == "Shipped" else db.time_left(o["ship_by"]))
        st.write(f"**Customer:** {o['customer_name']}, {o['city']} {o['pincode']}  |  **Channel:** {o['channel']}")
        if pd.notna(o["blocked_reason"]):
            st.error(f"Blocked: {o['blocked_reason']}")
        st.write("**Items in this order**")
        st.dataframe(db.get_order_items(chosen), hide_index=True)
        order_issues = db.get_order_issues(chosen)
        if len(order_issues):
            st.write("**Reported issues**")
            st.dataframe(order_issues, hide_index=True)
    else:
        st.info("No orders match these filters.")


def show_pick_pack():
    orders = db.get_orders()

    st.title("Pick & Pack")
    st.caption("Work from the top. Priority orders and the earliest deadlines come first.")

    def queue(statuses):
        q = orders[orders["status"].isin(statuses)]
        return q.sort_values(["is_priority", "ship_by"], ascending=[False, True])

    # ---------- PICK ----------
    st.subheader("1. To pick")
    to_pick = queue(["Received", "Processed", "Picking"])
    if to_pick.empty:
        st.success("Nothing waiting to be picked.")
    for _, o in to_pick.iterrows():
        tag = "⭐ PRIORITY  " if o["is_priority"] == 1 else ""
        with st.container(border=True):
            st.markdown(f"**{tag}{o['order_id']}**  |  {o['courier']}  |  {db.time_left(o['ship_by'])}")
            if pd.notna(o["blocked_reason"]):
                st.error(f"BLOCKED: {o['blocked_reason']}. Do not pick yet. Tell the office team.")
            st.dataframe(
                db.get_order_items_with_lookalikes(o["order_id"])[["name", "variant", "qty", "shelf"]],
                hide_index=True,
            )
            if pd.isna(o["blocked_reason"]):
                if st.button("✅ All items picked", key="pick_" + o["order_id"]):
                    db.move_order(o["order_id"], "Packing")
                    st.rerun()

    # ---------- PACK ----------
    st.subheader("2. To pack")
    to_pack = queue(["Packing"])
    if to_pack.empty:
        st.success("Nothing waiting to be packed.")
    for _, o in to_pack.iterrows():
        tag = "⭐ PRIORITY  " if o["is_priority"] == 1 else ""
        with st.container(border=True):
            st.markdown(f"**{tag}{o['order_id']}**  |  {o['courier']}  |  {db.time_left(o['ship_by'])}")
            items = db.get_order_items_with_lookalikes(o["order_id"])
            ok_to_pack = True
            for i, item in items.iterrows():
                st.markdown(f"**{item['qty']} x {item['name']} - {item['variant']}**  (Shelf {item['shelf']})")
                if pd.notna(item["lookalike_variant"]):
                    st.warning(f"Look-alike warning: this is NOT the {item['lookalike_variant']}")
                confirmed = st.checkbox(
                    f"I checked it is exactly: {item['variant']}",
                    key=f"chk_{o['order_id']}_{i}",
                )
                ok_to_pack = ok_to_pack and confirmed
            bay = st.selectbox(
                "Which bay will the box go to?",
                ["Bay A1", "Bay A2", "Bay B1", "Bay B2", "Bay C1", "Bay C2"],
                key="bay_" + o["order_id"],
            )
            if st.button("📦 Packed - move to pickup area", key="pack_" + o["order_id"], disabled=not ok_to_pack):
                db.move_order(o["order_id"], "Staged", bay)
                st.rerun()

def show_pickups():
    orders = db.get_orders()
    couriers = db.run_query("SELECT * FROM couriers")

    st.title("Pickups")
    st.caption("Packed boxes waiting for the courier. Check every box has a location.")

    staged = orders[orders["status"] == "Staged"]
    if staged.empty:
        st.success("No boxes waiting for pickup.")

    for _, c in couriers.iterrows():
        boxes = staged[staged["courier"] == c["courier"]].sort_values(["is_priority", "ship_by"], ascending=[False, True])
        if boxes.empty:
            continue
        cutoff = db.DEMO_NOW.replace(
            hour=int(c["cutoff_time"][:2]), minute=int(c["cutoff_time"][3:]), second=0
        )
        mins = int((cutoff - db.DEMO_NOW).total_seconds() // 60)

        st.subheader(f"{c['courier']}  |  pickup at {c['cutoff_time']}")
        if mins < 0:
            st.error(f"Pickup time has passed ({-mins} min ago).")
        elif mins <= 60:
            st.warning(f"Pickup in {mins} minutes. Make sure every box is at its bay.")
        else:
            st.info(f"Pickup in {mins // 60}h {mins % 60}m.")

        rows = []
        for _, b in boxes.iterrows():
            if b["bay_location"] == "Not found":
                note = "MISPLACED - find this box"
            elif b["ship_by"] < db.DEMO_NOW:
                note = "MISSED PICKUP - overdue, call courier"
            else:
                note = "OK"
            rows.append({
                "Order": b["order_id"],
                "Priority": "⭐ PRIORITY" if b["is_priority"] == 1 else "",
                "Bay": b["bay_location"],
                "Customer": b["customer_name"],
                "Check": note,
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True)

        if st.button(f"🚚 {c['courier']} collected these boxes", key="ship_" + c["courier"]):
            db.ship_courier_orders(c["courier"])
            st.rerun()

def show_stock_issues():
    st.title("Stock & Issues")
    st.caption("Stock that needs action, and every problem reported so far.")

    # ---------- STOCK ----------
    st.subheader("Stock check")
    inv = db.get_inventory()
    rows = []
    for _, r in inv.iterrows():
        flags = []
        if r["main_qty"] != r["last_counted_qty"]:
            flags.append(f"COUNT MISMATCH (system {r['main_qty']}, counted {r['last_counted_qty']})")
        if r["last_counted_qty"] < r["reorder_level"]:
            if r["second_qty"] > 0:
                flags.append(f"MOVE {r['second_qty']} FROM 2ND WAREHOUSE")
            else:
                flags.append("LOW STOCK - reorder")
        rows.append({
            "Product": r["product_name"],
            "Variant": r["variant"],
            "Shelf": r["shelf_location"],
            "System says": r["main_qty"],
            "Counted": r["last_counted_qty"],
            "2nd warehouse": r["second_qty"],
            "Reorder level": r["reorder_level"],
            "Action needed": " | ".join(flags) if flags else "OK",
        })
    table = pd.DataFrame(rows)
    table = table.sort_values("Action needed", key=lambda s: s == "OK", kind="stable")

    def colour(row):
        if row["Action needed"] != "OK":
            return ["background-color: #fff3cd; color: #5c4a1f"] * len(row)
        return [""] * len(row)

    flagged = int((table["Action needed"] != "OK").sum())
    st.caption(f"{flagged} products need action (highlighted). 'System says' is the spreadsheet figure, 'Counted' is the last physical count.")
    st.dataframe(table.style.apply(colour, axis=1), hide_index=True)

    for _, r in inv.iterrows():
        if r["last_counted_qty"] < r["reorder_level"] and r["second_qty"] > 0:
            if st.button(
                f"Move {r['second_qty']} x {r['product_name']} ({r['variant']}) to the main warehouse",
                key="move_" + r["sku"],
            ):
                db.transfer_stock(r["sku"])
                st.rerun()

    # ---------- ISSUES ----------
    st.subheader("Problem log")
    issues = db.get_all_issues()
    open_count = int((issues["status"] != "Resolved").sum())
    st.caption(f"{open_count} problems are still open or in progress. Open ones are listed first.")
    st.dataframe(
        issues[["issue_id", "order_id", "issue_type", "description", "owner", "status", "reported_at"]],
        hide_index=True,
    )

    st.write("**Update a problem**")
    chosen = st.selectbox("Which problem?", issues["issue_id"])
    new_status = st.selectbox("New status", ["Open", "In progress", "Resolved"])
    if st.button("Save status"):
        db.update_issue_status(chosen, new_status)
        st.rerun()

        st.write("**Report a new problem**")

    # A counter that changes after every report, which gives us fresh blank boxes
    if "form_n" not in st.session_state:
        st.session_state.form_n = 0
    n = st.session_state.form_n

    if "report_msg" in st.session_state:
        st.success(st.session_state.pop("report_msg"))

    order_ids = db.get_orders()["order_id"].tolist()
    new_order = st.selectbox("Which order?", order_ids, key=f"new_order_{n}")
    new_type = st.selectbox(
        "Type of problem",
        ["Missing stock", "Wrong variant", "Misplaced box", "Missed pickup", "Other"],
        key=f"new_type_{n}",
    )
    new_desc = st.text_input("What happened?", key=f"new_desc_{n}")
    new_owner = st.text_input("Who will fix it?", key=f"new_owner_{n}")
    if st.button("Report problem", key=f"report_btn_{n}"):
        if new_desc.strip() and new_owner.strip():
            db.add_issue(new_order, new_type, new_desc.strip(), new_owner.strip())
            st.session_state.form_n += 1
            st.session_state.report_msg = f"Problem reported for {new_order}."
            st.rerun()
        else:
            st.warning("Please fill in what happened and who will fix it.")


if page == "Dashboard":
    show_dashboard()
elif page == "Orders":
    show_orders()
elif page == "Pick & Pack":
    show_pick_pack()
elif page == "Pickups":
    show_pickups()
else:
    show_stock_issues()