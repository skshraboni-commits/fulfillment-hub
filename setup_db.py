import os
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "fulfillment.db"

# Start fresh every time so the demo data is always identical
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

conn = sqlite3.connect(DB_FILE)
cur = conn.cursor()

# ---------- 1. CREATE THE TABLES ----------
cur.executescript("""
CREATE TABLE couriers (
    courier TEXT PRIMARY KEY,
    cutoff_time TEXT,
    cost_per_parcel INTEGER,
    delivery_days INTEGER
);

CREATE TABLE products (
    sku TEXT PRIMARY KEY,
    product_name TEXT,
    variant TEXT,
    shelf_location TEXT,
    lookalike_sku TEXT
);

CREATE TABLE inventory (
    sku TEXT PRIMARY KEY,
    main_qty INTEGER,
    second_qty INTEGER,
    last_counted_qty INTEGER,
    reorder_level INTEGER
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    channel TEXT,
    customer_name TEXT,
    city TEXT,
    pincode TEXT,
    created_at TEXT,
    status TEXT,
    is_priority INTEGER,
    courier TEXT,
    ship_by TEXT,
    blocked_reason TEXT,
    bay_location TEXT,
    shipped_at TEXT
);

CREATE TABLE order_items (
    order_id TEXT,
    sku TEXT,
    quantity INTEGER
);

CREATE TABLE issues (
    issue_id TEXT PRIMARY KEY,
    order_id TEXT,
    issue_type TEXT,
    description TEXT,
    owner TEXT,
    status TEXT,
    reported_at TEXT
);
""")

# ---------- 2. COURIERS ----------
couriers = [
    ("FastTrack", "15:00", 80, 1),
    ("SwiftShip", "17:00", 55, 2),
    ("EconoPost", "18:00", 35, 4),
]
cur.executemany("INSERT INTO couriers VALUES (?,?,?,?)", couriers)
CUTOFF = {c[0]: c[1] for c in couriers}

# ---------- 3. PRODUCTS ----------
# The last column points to a look-alike variant that is easy to confuse
products = [
    ("TSH-BLU-M", "Cotton T-Shirt", "Blue / M", "A1-02", "TSH-BLU-L"),
    ("TSH-BLU-L", "Cotton T-Shirt", "Blue / L", "A1-03", "TSH-BLU-M"),
    ("TSH-BLK-M", "Cotton T-Shirt", "Black / M", "A1-04", None),
    ("BTL-500-STL", "Steel Bottle", "500 ml", "B2-01", "BTL-750-STL"),
    ("BTL-750-STL", "Steel Bottle", "750 ml", "B2-02", "BTL-500-STL"),
    ("CASE-14-BLK", "Phone Case", "iPhone 14 / Black", "C1-01", "CASE-14P-BLK"),
    ("CASE-14P-BLK", "Phone Case", "iPhone 14 Pro / Black", "C1-02", "CASE-14-BLK"),
    ("EAR-WHT", "Wireless Earbuds", "White", "D1-01", None),
    ("CHG-20W", "Fast Charger", "20 W", "D1-02", None),
    ("NTB-A5-RUL", "Notebook A5", "Ruled", "E1-01", "NTB-A5-PLN"),
    ("NTB-A5-PLN", "Notebook A5", "Plain", "E1-02", "NTB-A5-RUL"),
    ("MUG-WHT", "Ceramic Mug", "White", "F1-01", None),
]
cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

# ---------- 4. INVENTORY ----------
# sku, main_qty (what the spreadsheet says), second_qty,
# last_counted_qty (what someone physically counted), reorder_level
inventory = [
    ("TSH-BLU-M", 40, 0, 40, 10),
    ("TSH-BLU-L", 25, 0, 25, 10),
    ("TSH-BLK-M", 1, 30, 1, 10),      # stock is in the second warehouse
    ("BTL-500-STL", 50, 0, 48, 15),
    ("BTL-750-STL", 30, 0, 30, 10),
    ("CASE-14-BLK", 22, 0, 22, 10),
    ("CASE-14P-BLK", 12, 0, 12, 10),
    ("EAR-WHT", 15, 0, 9, 10),        # discrepancy: 6 earbuds missing
    ("CHG-20W", 60, 0, 60, 20),
    ("NTB-A5-RUL", 5, 0, 5, 12),      # low stock
    ("NTB-A5-PLN", 35, 0, 35, 10),
    ("MUG-WHT", 6, 0, 0, 10),         # system says 6, shelf has 0
]
cur.executemany("INSERT INTO inventory VALUES (?,?,?,?,?)", inventory)

# ---------- 5. ORDERS ----------
# Demo "now" is 5 Oct 2026, 2:30 PM (the app will use this fixed clock)
orders = [
    # --- Story orders: each one demonstrates a specific problem ---
    ("ORD-1001", "Amazon", "Priya Sharma", "Kolkata", "700001", "2026-10-05 08:15", "Picking", 1, "FastTrack", "2026-10-05 15:00", "Stock in second warehouse - transfer needed", None, None),
    ("ORD-1002", "Flipkart", "Rahul Verma", "Howrah", "711101", "2026-10-05 08:40", "Packing", 1, "FastTrack", "2026-10-05 15:00", None, None, None),
    ("ORD-1003", "Amazon", "Neha Gupta", "Durgapur", "713201", "2026-10-05 13:05", "Received", 1, "SwiftShip", "2026-10-05 17:00", None, None, None),
    ("ORD-1004", "Meesho", "Arjun Das", "Kolkata", "700019", "2026-10-05 09:10", "Staged", 1, "FastTrack", "2026-10-05 15:00", None, "Bay A1", None),
    ("ORD-1005", "Amazon", "Sneha Roy", "Siliguri", "734001", "2026-10-04 16:00", "Picking", 0, "EconoPost", "2026-10-04 18:00", "Stock not found on shelf", None, None),
    ("ORD-1006", "Flipkart", "Imran Khan", "Asansol", "713301", "2026-10-04 15:30", "Packing", 0, "SwiftShip", "2026-10-04 17:00", None, None, None),
    ("ORD-1007", "Meesho", "Kavita Singh", "Kolkata", "700091", "2026-10-04 11:00", "Staged", 0, "FastTrack", "2026-10-04 15:00", None, "Bay A2", None),
    ("ORD-1008", "Amazon", "Deepak Nair", "Kolkata", "700064", "2026-10-05 07:50", "Staged", 0, "SwiftShip", "2026-10-05 17:00", None, "Not found", None),
    ("ORD-1009", "Flipkart", "Pooja Mehta", "Howrah", "711102", "2026-10-05 10:00", "Packing", 0, "EconoPost", "2026-10-05 18:00", None, None, None),
    ("ORD-1010", "Amazon", "Sanjay Ghosh", "Kolkata", "700032", "2026-10-04 09:00", "Shipped", 1, "FastTrack", "2026-10-04 15:00", None, None, "2026-10-05 09:30"),
    # --- Boxes waiting at bays for courier pickup ---
    ("ORD-1011", "Amazon", "Meera Iyer", "Kolkata", "700020", "2026-10-05 08:00", "Staged", 0, "SwiftShip", "2026-10-05 17:00", None, "Bay B1", None),
    ("ORD-1012", "Flipkart", "Karan Malik", "Howrah", "711103", "2026-10-05 08:20", "Staged", 0, "SwiftShip", "2026-10-05 17:00", None, "Bay B2", None),
    ("ORD-1013", "Meesho", "Anjali Rao", "Durgapur", "713202", "2026-10-05 08:45", "Staged", 0, "EconoPost", "2026-10-05 18:00", None, "Bay C1", None),
    ("ORD-1014", "Amazon", "Farhan Ali", "Kolkata", "700045", "2026-10-05 09:00", "Staged", 0, "EconoPost", "2026-10-05 18:00", None, "Bay C1", None),
    ("ORD-1015", "Flipkart", "Tanvi Shah", "Siliguri", "734002", "2026-10-05 09:30", "Staged", 0, "EconoPost", "2026-10-05 18:00", None, "Bay C2", None),
    ("ORD-1016", "Amazon", "Vivek Pal", "Kolkata", "700010", "2026-10-05 09:50", "Staged", 1, "FastTrack", "2026-10-05 15:00", None, "Bay A1", None),
]

# --- Filler orders ORD-1017 to ORD-1040: realistic volume across stages ---
channels = ["Amazon", "Flipkart", "Meesho"]
names = ["Aman Joshi", "Ritu Paul", "Vikram Sen", "Ishita Bose", "Rohan Dutta", "Tania Saha"]
places = [("Kolkata", "700001"), ("Howrah", "711101"), ("Durgapur", "713201"),
          ("Siliguri", "734001"), ("Asansol", "713301")]
courier_cycle = ["SwiftShip", "EconoPost", "FastTrack", "EconoPost"]
statuses = (["Shipped"] * 8 + ["Received"] * 4 + ["Processed"] * 4
            + ["Picking"] * 4 + ["Packing"] * 4)

fmt = "%Y-%m-%d %H:%M"
created_base = datetime(2026, 10, 5, 6, 30)
shipped_base = datetime(2026, 10, 5, 9, 30)

for i, status in enumerate(statuses):
    order_id = f"ORD-{1017 + i}"
    courier = courier_cycle[i % 4]
    city, pin = places[i % 5]
    created = (created_base + timedelta(minutes=15 * i)).strftime(fmt)
    ship_by = f"2026-10-05 {CUTOFF[courier]}"
    shipped_at = None
    if status == "Shipped":
        shipped_at = (shipped_base + timedelta(minutes=30 * i)).strftime(fmt)
    priority = 1 if (status == "Shipped" and i % 4 == 0) else 0
    orders.append((order_id, channels[i % 3], names[i % 6], city, pin, created,
                   status, priority, courier, ship_by, None, None, shipped_at))

cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", orders)

# ---------- 6. ORDER ITEMS ----------
items = {
    "ORD-1001": [("TSH-BLK-M", 2)],
    "ORD-1002": [("CASE-14-BLK", 1), ("CHG-20W", 1)],
    "ORD-1003": [("EAR-WHT", 1)],
    "ORD-1004": [("BTL-500-STL", 1)],
    "ORD-1005": [("MUG-WHT", 2)],
    "ORD-1006": [("NTB-A5-RUL", 3)],
    "ORD-1007": [("TSH-BLU-L", 1)],
    "ORD-1008": [("CHG-20W", 2)],
    "ORD-1009": [("BTL-750-STL", 1)],
    "ORD-1010": [("CASE-14P-BLK", 1)],
}
safe_skus = ["TSH-BLU-M", "TSH-BLU-L", "BTL-500-STL", "BTL-750-STL", "CASE-14-BLK",
             "CASE-14P-BLK", "CHG-20W", "NTB-A5-PLN"]
item_rows = []
n = 0
for o in orders:
    oid = o[0]
    if oid in items:
        for sku, qty in items[oid]:
            item_rows.append((oid, sku, qty))
    else:
        item_rows.append((oid, safe_skus[n % len(safe_skus)], 1 + n % 2))
        n += 1
cur.executemany("INSERT INTO order_items VALUES (?,?,?)", item_rows)

# ---------- 7. ISSUES ----------
issues = [
    ("ISS-01", "ORD-1001", "Missing stock", "Only 1 black T-shirt (M) in main warehouse, 30 in second warehouse. Transfer needed.", "Ravi", "In progress", "2026-10-05 13:50"),
    ("ISS-02", "ORD-1005", "Missing stock", "System shows 6 white mugs, shelf count is 0.", "Anita", "Open", "2026-10-04 17:30"),
    ("ISS-03", "ORD-1007", "Missed pickup", "FastTrack did not collect this box yesterday.", "Meena", "Open", "2026-10-04 15:30"),
    ("ISS-04", "ORD-1008", "Misplaced box", "Packed box is not at its bay. Last seen near packing table.", "Ravi", "Open", "2026-10-05 11:00"),
    ("ISS-05", "ORD-1009", "Wrong variant", "500 ml bottle sits next to the 750 ml bottle on the shelf. Customer ordered 750 ml.", "Suresh", "In progress", "2026-10-05 13:15"),
    ("ISS-06", "ORD-1010", "Other", "Label printed with wrong courier, reprinted. Shipped late as a result.", "Anita", "Resolved", "2026-10-05 09:00"),
]
cur.executemany("INSERT INTO issues VALUES (?,?,?,?,?,?,?)", issues)

conn.commit()

# ---------- 8. QUICK CHECK ----------
print("Database created:", DB_FILE)
for table in ["orders", "order_items", "products", "inventory", "issues", "couriers"]:
    count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count} rows")
print("Orders by status:")
for s in ["Received", "Processed", "Picking", "Packing", "Staged", "Shipped"]:
    count = cur.execute("SELECT COUNT(*) FROM orders WHERE status = ?", (s,)).fetchone()[0]
    print(f"  {s}: {count}")

conn.close()