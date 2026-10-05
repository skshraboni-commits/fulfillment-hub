# Fulfillment Hub

A simple fulfillment operations app for XYZ, an e-commerce business that
currently runs its warehouse on spreadsheets and shared folders.
Built as a take-home project for an Operations Analyst role.

## Problem

XYZ ships about 200-300 orders a day with a small office team and
2-3 warehouse workers. As it grows, the spreadsheet process breaks down:

- Order status is hard to see at a glance
- Delays go unnoticed
- Priority (same-day) orders get mixed in with regular orders
- Stock in the spreadsheet cannot be found or has gone missing
- The wrong product or variant is sometimes shipped
- Packed boxes are misplaced, or the courier misses the pickup
- Problems are handled informally and forgotten

The warehouse team is experienced but not very comfortable with technology,
so the app is designed to be simple, with plain-language labels.

## Solution

One app with five screens. Each screen exists to fix one or more of the
problems above.

| Problem | Where it is addressed |
|---|---|
| Can't see order status | **Orders**: search, filters, order detail |
| Delays unnoticed, priority orders buried | **Dashboard**: red warning banner, KPIs, "Needs attention" list; priority orders always sorted first |
| Stock missing or in the second warehouse | **Stock & Issues**: system count vs physical count, low-stock flags, one-click transfer from the second warehouse that unblocks waiting orders |
| Wrong product or variant shipped | **Pick & Pack**: look-alike variant warning, and packing is blocked until the worker confirms the exact variant |
| Boxes misplaced, courier misses pickup | **Pickups**: boxes grouped by courier with cut-off countdown, bay location, and misplaced / missed-pickup warnings |
| Problems handled informally | **Stock & Issues**: problem log with type, owner and status |

## Key features

- Dashboard with 6 KPIs and a "Needs attention" list
- Order pipeline: Received, Processed, Picking, Packing, Staged, Shipped
- Priority orders sorted first everywhere; overdue orders shown in red
- Orders that are blocked by stock show the reason and cannot be picked
- Look-alike variant warnings and tick-to-confirm before packing
- Pickup countdown per courier; a misplaced box cannot be marked as shipped
- Problem log where anyone can report an issue and update its status
- "Reset demo data" button in the sidebar

### KPIs and how they are calculated

| KPI | Calculation |
|---|---|
| Overdue orders | Not shipped, and past the ship-by time |
| Priority at risk | Priority order, not yet staged, ship-by time within 2 hours |
| Blocked by stock | Not shipped, with a stock problem recorded on the order |
| Boxes awaiting pickup | Orders in Staged status |
| Open issues | Issues not marked Resolved |
| On-time shipment rate | Shipped orders that left before their ship-by time, divided by all shipped orders |

## Tech stack

- Python
- Streamlit (web interface)
- SQLite (database stored in a single file)
- Pandas (data handling and KPI calculations)

## How to run locally

You need Python installed.

1. Download or clone this repository.
2. Open a terminal in the project folder.
3. Install the requirements:
```
   pip install -r requirements.txt
```
4. Start the app:
```
   python -m streamlit run app.py
```
5. Open http://localhost:8501 in your browser.

The database is created automatically the first time the app starts.
To reset the demo data at any time, click **Reset demo data** in the
sidebar, or run `python setup_db.py`.

## Sample data

All data is made up for this demo (`setup_db.py` creates it): 40 orders,
12 product variants, 3 couriers, and 6 reported issues. It is designed to
show each problem from the brief:

- Priority orders close to their courier cut-off
- Stock sitting in the second warehouse (black T-shirt: 1 in main, 30 in second)
- Stock the system says exists but is not on the shelf (white mugs)
- Count mismatches and low-stock items
- Look-alike variants (bottle sizes, phone case models, notebook types)
- Overdue orders, a missed courier pickup, and a misplaced packed box
- A late shipment, so the on-time rate is realistic

## Assumptions

The brief does not specify these, so they are my assumptions:

- The demo clock is fixed at **5 Oct 2026, 14:30**, so the dashboard looks the
  same whenever it is opened.
- Three couriers with pickup cut-offs of 15:00 (FastTrack), 17:00 (SwiftShip)
  and 18:00 (EconoPost).
- A priority order's deadline is its courier's same-day cut-off.
- "Priority at risk" means less than 2 hours to the deadline.
- 40 demo orders are enough to show the idea, even though real volume
  is 200-300 a day.
- No user logins.
- Only city and pincode are stored for the destination, not the full address.

## What I chose not to build

- Real courier or marketplace integrations
- Generating real shipping labels
- User accounts and permissions
- Barcode scanning
- Receiving inbound deliveries
- Courier cost or speed optimisation

These do not directly cause the late, lost or wrong orders described in the brief.

## Limitations

- All visitors share one demo database, so one person's changes can appear
  for another. The Reset button restores the original data.
- The demo clock is fixed, so deadlines do not count down in real time.

## Future improvements

- A shared production database with user accounts
- Barcode scanning at pick and pack
- Courier suggestions based on destination city and delivery speed
- Alerts by message when a priority order is at risk
- Receiving inbound deliveries and stock put-away
- Trends over time (on-time rate by week, common issue types)
