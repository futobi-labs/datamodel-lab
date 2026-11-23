#!/usr/bin/env python3
"""Build data/sample-model.json, the metadata every exploration reads.

The sample is a small, generic order-to-cash + inventory model laid out the
way a Fabric lakehouse/warehouse usually is:

  source -> bronze -> silver -> gold (star) -> semantic model -> reports

Everything the explorations draw comes from the JSON this writes, so to look
at your own model, replace this script (or the JSON) with metadata exported
from your platform: INFORMATION_SCHEMA, a pipeline config table, a TMDL/BIM
export of a semantic model, or Purview lineage. The shape is documented in
model/index.html and README.md.

Run:  python3 tools/build_sample_model.py
"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "sample-model.json"

LAYERS = [
    {"id": "source", "name": "Source", "order": 0, "platform": "Operational systems",
     "fabric": "ERP database, CRM API, files", "description": "Systems of record. Owned by someone else; read, never written."},
    {"id": "bronze", "name": "Bronze", "order": 1, "platform": "Lakehouse (Files / shortcuts / views)",
     "fabric": "Shortcuts, mirrored tables, pipeline copies", "description": "Raw, source-shaped, append-friendly. Adds only audit columns."},
    {"id": "silver", "name": "Silver", "order": 2, "platform": "Lakehouse Delta tables",
     "fabric": "Notebooks or Warehouse T-SQL", "description": "Cleaned, typed, de-duplicated, conformed business entities."},
    {"id": "gold", "name": "Gold", "order": 3, "platform": "Warehouse (star schema)",
     "fabric": "Warehouse tables loaded by stored procedures", "description": "Dimensional model at declared grain: facts, dimensions, surrogate keys."},
    {"id": "semantic", "name": "Semantic model", "order": 4, "platform": "Power BI semantic model",
     "fabric": "Direct Lake semantic model", "description": "Relationships, measures, hierarchies and friendly names on top of gold."},
    {"id": "report", "name": "Reports", "order": 5, "platform": "Power BI reports",
     "fabric": "Reports, Excel, notebooks via semantic link", "description": "Visuals that ask the semantic model questions."},
]

tables = []
col_edges = []      # {from, to, transform}


def T(layer, schema, name, kind, cols, **extra):
    """Register a table. cols: list of (name, type, key, description)."""
    t = {"id": f"{layer}.{schema}.{name}" if layer in ("source",) else f"{layer}.{name}",
         "layer": layer, "schema": schema, "name": name, "kind": kind,
         "columns": [{"name": c[0], "type": c[1], **({"key": c[2]} if c[2] else {}),
                      **({"description": c[3]} if len(c) > 3 and c[3] else {})} for c in cols]}
    t.update(extra)
    tables.append(t)
    return t["id"]


def E(src, dst, transform="pass-through"):
    col_edges.append({"from": src, "to": dst, "transform": transform})


# --------------------------------------------------------------------- source
SRC = {}
SRC["soh"] = T("source", "erp", "sales_order_header", "source", [
    ("order_id", "int", "PK"), ("order_number", "varchar(20)", "BK"), ("customer_id", "int", "FK"),
    ("salesperson_id", "varchar(12)", "FK"), ("warehouse_id", "int", "FK"), ("order_date", "datetime", None),
    ("ship_date", "datetime", None), ("status", "char(1)", None, "O/S/C/X codes"), ("currency_code", "char(3)", None),
    ("modified_at", "datetime", None, "change tracking watermark")],
    system="ERP (SQL Server)", description="Order headers.")
SRC["sol"] = T("source", "erp", "sales_order_line", "source", [
    ("order_id", "int", "PK"), ("line_number", "smallint", "PK"), ("product_id", "int", "FK"),
    ("quantity", "decimal(12,3)", None), ("unit_price", "decimal(12,4)", None), ("discount_pct", "decimal(5,4)", None),
    ("line_status", "char(1)", None), ("modified_at", "datetime", None)],
    system="ERP (SQL Server)", description="Order lines.")
SRC["cus"] = T("source", "erp", "customer", "source", [
    ("customer_id", "int", "PK"), ("customer_name", "nvarchar(200)", None), ("segment_code", "char(2)", None),
    ("region_code", "char(3)", None), ("city", "nvarchar(100)", None), ("state", "char(2)", None),
    ("created_at", "datetime", None), ("modified_at", "datetime", None)],
    system="ERP (SQL Server)", description="Customer master.")
SRC["prd"] = T("source", "erp", "product", "source", [
    ("product_id", "int", "PK"), ("sku", "varchar(30)", "BK"), ("product_name", "nvarchar(200)", None),
    ("category", "nvarchar(60)", None), ("subcategory", "nvarchar(60)", None), ("color", "nvarchar(30)", None),
    ("list_price", "decimal(12,4)", None), ("standard_cost", "decimal(12,4)", None), ("modified_at", "datetime", None)],
    system="ERP (SQL Server)", description="Product master.")
SRC["whs"] = T("source", "erp", "warehouse", "source", [
    ("warehouse_id", "int", "PK"), ("warehouse_name", "nvarchar(100)", None), ("city", "nvarchar(100)", None),
    ("state", "char(2)", None)], system="ERP (SQL Server)", description="Warehouse list.")
SRC["inv"] = T("source", "erp", "inventory_txn", "source", [
    ("txn_id", "bigint", "PK"), ("product_id", "int", "FK"), ("warehouse_id", "int", "FK"), ("txn_date", "datetime", None),
    ("qty_change", "decimal(12,3)", None), ("txn_type", "varchar(10)", None, "RECEIPT/SHIP/ADJ")],
    system="ERP (SQL Server)", description="Inventory movements.")
SRC["rep"] = T("source", "crm", "salesperson", "source", [
    ("rep_id", "string", "PK"), ("full_name", "string", None), ("team", "string", None), ("region", "string", None),
    ("hire_date", "string", None, "ISO date as text")], system="CRM (REST API, JSON)", description="Sales reps.")
SRC["bud"] = T("source", "files", "budget", "source", [
    ("fiscal_month", "string", None, "YYYY-MM"), ("category", "string", None), ("region", "string", None),
    ("budget_amount", "string", None)], system="Finance (monthly CSV drop)", description="Budget by month, category, region.")

# --------------------------------------------------------------------- bronze
BRZ = {}
ingest = {"soh": "shortcut", "sol": "shortcut", "cus": "shortcut", "prd": "shortcut", "whs": "shortcut",
          "inv": "copy (incremental)", "rep": "copy (API)", "bud": "copy (file)"}
for key, sid in SRC.items():
    st = next(t for t in tables if t["id"] == sid)
    bname = f"{st['schema']}_{st['name']}"
    cols = [(c["name"], c["type"], c.get("key")) for c in st["columns"]]
    cols += [("_ingested_at", "timestamp", None, "audit"), ("_batch_id", "string", None, "audit")]
    BRZ[key] = T("bronze", "bronze", bname, "raw", cols, ingest=ingest[key],
                 description=f"Raw {st['schema']}.{st['name']} as landed ({ingest[key]}). Source-shaped, nothing renamed.")
    for c in st["columns"]:
        E(f"{sid}.{c['name']}", f"{BRZ[key]}.{c['name']}")

# --------------------------------------------------------------------- silver
SIL = {}
SIL["sol"] = T("silver", "silver", "sales_order_line", "entity", [
    ("order_id", "int", "PK"), ("line_number", "int", "PK"), ("order_number", "string", "BK"), ("customer_id", "int", "FK"),
    ("salesperson_id", "string", "FK"), ("product_id", "int", "FK"), ("warehouse_id", "int", "FK"),
    ("order_date", "date", None), ("ship_date", "date", None), ("order_status", "string", None),
    ("currency_code", "string", None), ("quantity", "decimal(12,3)", None), ("unit_price", "decimal(12,4)", None),
    ("discount_pct", "decimal(5,4)", None), ("gross_amount", "decimal(18,4)", None), ("net_amount", "decimal(18,4)", None),
    ("_modified_at", "timestamp", None)],
    grain="One row per order line", description="Header joined to lines, typed, status decoded, amounts derived.")
h, l, s = BRZ["soh"], BRZ["sol"], SIL["sol"]
for c in ["order_id"]:
    E(f"{h}.{c}", f"{s}.{c}", "join key"); E(f"{l}.{c}", f"{s}.{c}", "join key")
E(f"{l}.line_number", f"{s}.line_number", "cast")
for c in ["order_number", "customer_id", "salesperson_id", "warehouse_id", "currency_code"]:
    E(f"{h}.{c}", f"{s}.{c}")
E(f"{h}.order_date", f"{s}.order_date", "cast to date"); E(f"{h}.ship_date", f"{s}.ship_date", "cast to date")
E(f"{h}.status", f"{s}.order_status", "decode O/S/C/X")
for c in ["product_id", "quantity", "unit_price", "discount_pct"]:
    E(f"{l}.{c}", f"{s}.{c}")
E(f"{l}.quantity", f"{s}.gross_amount", "quantity * unit_price"); E(f"{l}.unit_price", f"{s}.gross_amount", "quantity * unit_price")
for c in ["quantity", "unit_price", "discount_pct"]:
    E(f"{l}.{c}", f"{s}.net_amount", "qty * price * (1 - discount)")
E(f"{h}.modified_at", f"{s}._modified_at", "greatest(header, line)"); E(f"{l}.modified_at", f"{s}._modified_at", "greatest(header, line)")

SIL["cus"] = T("silver", "silver", "customer", "entity", [
    ("customer_id", "int", "PK"), ("customer_name", "string", None), ("segment", "string", None), ("region", "string", None),
    ("city", "string", None), ("state", "string", None), ("created_date", "date", None), ("_modified_at", "timestamp", None),
    ("_row_hash", "string", None, "hash of tracked attributes for SCD2 change detection")],
    grain="One row per customer (current state)", description="Trimmed, de-duplicated, codes decoded.")
b, s = BRZ["cus"], SIL["cus"]
E(f"{b}.customer_id", f"{s}.customer_id"); E(f"{b}.customer_name", f"{s}.customer_name", "trim, proper case")
E(f"{b}.segment_code", f"{s}.segment", "lookup segment code"); E(f"{b}.region_code", f"{s}.region", "lookup region code")
E(f"{b}.city", f"{s}.city"); E(f"{b}.state", f"{s}.state", "upper")
E(f"{b}.created_at", f"{s}.created_date", "cast to date"); E(f"{b}.modified_at", f"{s}._modified_at")
for c in ["customer_name", "segment_code", "region_code", "city", "state"]:
    E(f"{b}.{c}", f"{s}._row_hash", "sha2 of tracked columns")

SIL["prd"] = T("silver", "silver", "product", "entity", [
    ("product_id", "int", "PK"), ("sku", "string", "BK"), ("product_name", "string", None), ("category", "string", None),
    ("subcategory", "string", None), ("color", "string", None), ("list_price", "decimal(12,4)", None),
    ("standard_cost", "decimal(12,4)", None), ("_modified_at", "timestamp", None)],
    grain="One row per product", description="Typed product master; blank colors set to 'n/a'.")
b, s = BRZ["prd"], SIL["prd"]
for c in ["product_id", "sku", "product_name", "category", "subcategory", "list_price", "standard_cost"]:
    E(f"{b}.{c}", f"{s}.{c}")
E(f"{b}.color", f"{s}.color", "coalesce to 'n/a'"); E(f"{b}.modified_at", f"{s}._modified_at")

SIL["whs"] = T("silver", "silver", "warehouse", "entity", [
    ("warehouse_id", "int", "PK"), ("warehouse_name", "string", None), ("city", "string", None), ("state", "string", None)],
    grain="One row per warehouse", description="Warehouse list.")
for c in ["warehouse_id", "warehouse_name", "city", "state"]:
    E(f"{BRZ['whs']}.{c}", f"{SIL['whs']}.{c}")

SIL["inv"] = T("silver", "silver", "inventory_txn", "entity", [
    ("txn_id", "bigint", "PK"), ("product_id", "int", "FK"), ("warehouse_id", "int", "FK"), ("txn_date", "date", None),
    ("qty_in", "decimal(12,3)", None), ("qty_out", "decimal(12,3)", None), ("txn_type", "string", None)],
    grain="One row per inventory movement", description="Signed quantity split into in/out.")
b, s = BRZ["inv"], SIL["inv"]
for c in ["txn_id", "product_id", "warehouse_id", "txn_type"]:
    E(f"{b}.{c}", f"{s}.{c}")
E(f"{b}.txn_date", f"{s}.txn_date", "cast to date")
E(f"{b}.qty_change", f"{s}.qty_in", "greatest(qty, 0)"); E(f"{b}.qty_change", f"{s}.qty_out", "greatest(-qty, 0)")

SIL["rep"] = T("silver", "silver", "salesperson", "entity", [
    ("salesperson_id", "string", "PK"), ("salesperson_name", "string", None), ("team", "string", None),
    ("region", "string", None), ("hire_date", "date", None)],
    grain="One row per sales rep", description="Flattened from JSON, renamed to the enterprise vocabulary.")
b, s = BRZ["rep"], SIL["rep"]
E(f"{b}.rep_id", f"{s}.salesperson_id", "rename"); E(f"{b}.full_name", f"{s}.salesperson_name", "rename")
E(f"{b}.team", f"{s}.team"); E(f"{b}.region", f"{s}.region"); E(f"{b}.hire_date", f"{s}.hire_date", "parse ISO date")

SIL["bud"] = T("silver", "silver", "budget", "entity", [
    ("month_start", "date", "PK"), ("category", "string", "PK"), ("region", "string", "PK"), ("budget_amount", "decimal(18,2)", None)],
    grain="One row per month x category x region", description="CSV typed and validated; months as first-of-month dates.")
b, s = BRZ["bud"], SIL["bud"]
E(f"{b}.fiscal_month", f"{s}.month_start", "parse YYYY-MM to date"); E(f"{b}.category", f"{s}.category")
E(f"{b}.region", f"{s}.region"); E(f"{b}.budget_amount", f"{s}.budget_amount", "cast decimal")

# --------------------------------------------------------------------- gold
GLD = {}
GLD["date"] = T("gold", "dbo", "dim_date", "dimension", [
    ("date_key", "int", "SK", "yyyymmdd"), ("calendar_date", "date", "BK"), ("month_start", "date", None), ("month_name", "varchar", None),
    ("quarter", "varchar", None), ("fiscal_year", "int", None), ("is_weekend", "bit", None)],
    grain="One row per calendar day", scd="Type 0 (generated)", generated=True,
    description="Generated calendar. Role-plays as order date, ship date, snapshot date and budget month.")
GLD["cus"] = T("gold", "dbo", "dim_customer", "dimension", [
    ("customer_key", "int", "SK"), ("customer_id", "int", "BK"), ("customer_name", "varchar", None), ("segment", "varchar", None),
    ("region", "varchar", None), ("city", "varchar", None), ("state", "varchar", None),
    ("valid_from", "datetime2", None), ("valid_to", "datetime2", None), ("is_current", "bit", None)],
    grain="One row per customer version", scd="Type 2 on segment, region, city, state; Type 1 on name",
    description="History-tracked customer. Facts point at the version current when the order was placed.")
s, g = SIL["cus"], GLD["cus"]
E(f"{s}.customer_id", f"{g}.customer_key", "surrogate key (identity)")
for c in ["customer_id", "customer_name", "segment", "region", "city", "state"]:
    E(f"{s}.{c}", f"{g}.{c}")
E(f"{s}._row_hash", f"{g}.valid_from", "SCD2: change detected via row hash"); E(f"{s}._modified_at", f"{g}.valid_from", "SCD2 effective date")
E(f"{s}._row_hash", f"{g}.valid_to", "SCD2 expire"); E(f"{s}._row_hash", f"{g}.is_current", "SCD2 flag")

GLD["prd"] = T("gold", "dbo", "dim_product", "dimension", [
    ("product_key", "int", "SK"), ("product_id", "int", "BK"), ("sku", "varchar", None), ("product_name", "varchar", None),
    ("category", "varchar", None), ("subcategory", "varchar", None), ("color", "varchar", None), ("list_price", "decimal(12,4)", None)],
    grain="One row per product", scd="Type 1", description="Overwritten in place; current attributes only.")
s, g = SIL["prd"], GLD["prd"]
E(f"{s}.product_id", f"{g}.product_key", "surrogate key (identity)")
for c in ["product_id", "sku", "product_name", "category", "subcategory", "color", "list_price"]:
    E(f"{s}.{c}", f"{g}.{c}")

GLD["whs"] = T("gold", "dbo", "dim_warehouse", "dimension", [
    ("warehouse_key", "int", "SK"), ("warehouse_id", "int", "BK"), ("warehouse_name", "varchar", None), ("city", "varchar", None),
    ("state", "varchar", None)], grain="One row per warehouse", scd="Type 1", description="Warehouses.")
s, g = SIL["whs"], GLD["whs"]
E(f"{s}.warehouse_id", f"{g}.warehouse_key", "surrogate key (identity)")
for c in ["warehouse_id", "warehouse_name", "city", "state"]:
    E(f"{s}.{c}", f"{g}.{c}")

GLD["rep"] = T("gold", "dbo", "dim_salesperson", "dimension", [
    ("salesperson_key", "int", "SK"), ("salesperson_id", "varchar", "BK"), ("salesperson_name", "varchar", None),
    ("team", "varchar", None), ("region", "varchar", None)],
    grain="One row per sales rep", scd="Type 1", description="Sales reps from CRM, conformed to the ERP rep id.")
s, g = SIL["rep"], GLD["rep"]
E(f"{s}.salesperson_id", f"{g}.salesperson_key", "surrogate key (identity)")
for c in ["salesperson_id", "salesperson_name", "team", "region"]:
    E(f"{s}.{c}", f"{g}.{c}")

GLD["sales"] = T("gold", "dbo", "fact_sales", "fact", [
    ("order_date_key", "int", "FK"), ("ship_date_key", "int", "FK"), ("customer_key", "int", "FK"), ("product_key", "int", "FK"),
    ("warehouse_key", "int", "FK"), ("salesperson_key", "int", "FK"), ("order_number", "varchar", "DD", "degenerate dimension"),
    ("line_number", "int", "DD"), ("quantity", "decimal(12,3)", None), ("gross_amount", "decimal(18,4)", None),
    ("discount_amount", "decimal(18,4)", None), ("net_amount", "decimal(18,4)", None), ("cost_amount", "decimal(18,4)", None)],
    grain="One row per sales order line", fact_type="Transaction", additivity="All measures fully additive",
    description="Order lines with surrogate keys looked up at load time.")
s, g = SIL["sol"], GLD["sales"]
E(f"{s}.order_date", f"{g}.order_date_key", "lookup dim_date"); E(f"{s}.ship_date", f"{g}.ship_date_key", "lookup dim_date")
E(f"{s}.customer_id", f"{g}.customer_key", "lookup dim_customer as of order_date")
E(f"{s}.order_date", f"{g}.customer_key", "point-in-time SCD2 lookup")
E(f"{s}.product_id", f"{g}.product_key", "lookup dim_product"); E(f"{s}.warehouse_id", f"{g}.warehouse_key", "lookup dim_warehouse")
E(f"{s}.salesperson_id", f"{g}.salesperson_key", "lookup dim_salesperson")
E(f"{s}.order_number", f"{g}.order_number"); E(f"{s}.line_number", f"{g}.line_number"); E(f"{s}.quantity", f"{g}.quantity")
E(f"{s}.gross_amount", f"{g}.gross_amount"); E(f"{s}.net_amount", f"{g}.net_amount")
E(f"{s}.gross_amount", f"{g}.discount_amount", "gross - net"); E(f"{s}.net_amount", f"{g}.discount_amount", "gross - net")
E(f"{s}.quantity", f"{g}.cost_amount", "quantity * standard_cost"); E(f"{SIL['prd']}.standard_cost", f"{g}.cost_amount", "quantity * standard_cost")
for k in ("date", "cus", "prd", "whs", "rep"):
    pass

GLD["inv"] = T("gold", "dbo", "fact_inventory_daily", "fact", [
    ("snapshot_date_key", "int", "FK"), ("product_key", "int", "FK"), ("warehouse_key", "int", "FK"),
    ("qty_in", "decimal(12,3)", None), ("qty_out", "decimal(12,3)", None), ("on_hand_qty", "decimal(12,3)", None, "semi-additive: not across time")],
    grain="One row per product x warehouse x day", fact_type="Periodic snapshot",
    additivity="qty_in/qty_out additive; on_hand_qty semi-additive (not over time)",
    description="Daily position built from movements: running sum of in minus out.")
s, g = SIL["inv"], GLD["inv"]
E(f"{s}.txn_date", f"{g}.snapshot_date_key", "lookup dim_date"); E(f"{s}.product_id", f"{g}.product_key", "lookup dim_product")
E(f"{s}.warehouse_id", f"{g}.warehouse_key", "lookup dim_warehouse")
E(f"{s}.qty_in", f"{g}.qty_in", "sum per day"); E(f"{s}.qty_out", f"{g}.qty_out", "sum per day")
E(f"{s}.qty_in", f"{g}.on_hand_qty", "running sum (in - out)"); E(f"{s}.qty_out", f"{g}.on_hand_qty", "running sum (in - out)")

GLD["bud"] = T("gold", "dbo", "fact_budget", "fact", [
    ("month_date_key", "int", "FK", "first day of month"), ("category", "varchar", None, "joins dim_product at category grain"),
    ("region", "varchar", None, "joins customer region"), ("budget_amount", "decimal(18,2)", None)],
    grain="One row per month x product category x region", fact_type="Periodic snapshot (plan)",
    additivity="Additive", description="Plan at a coarser grain than sales: a shrunken view of Date and Product.")
s, g = SIL["bud"], GLD["bud"]
E(f"{s}.month_start", f"{g}.month_date_key", "lookup dim_date (first of month)"); E(f"{s}.category", f"{g}.category")
E(f"{s}.region", f"{g}.region"); E(f"{s}.budget_amount", f"{g}.budget_amount")

# ----------------------------------------------------------------- semantic
SEM = {}
sem_map = {
    "Date": (GLD["date"], [("Date", "calendar_date"), ("Month", "month_start"), ("Month Name", "month_name"), ("Quarter", "quarter"),
                           ("Fiscal Year", "fiscal_year"), ("date_key", "date_key")]),
    "Customer": (GLD["cus"], [("Customer", "customer_name"), ("Segment", "segment"), ("Region", "region"), ("City", "city"),
                              ("State", "state"), ("customer_key", "customer_key")]),
    "Product": (GLD["prd"], [("Product", "product_name"), ("SKU", "sku"), ("Category", "category"), ("Subcategory", "subcategory"),
                             ("Color", "color"), ("product_key", "product_key")]),
    "Warehouse": (GLD["whs"], [("Warehouse", "warehouse_name"), ("Warehouse State", "state"), ("warehouse_key", "warehouse_key")]),
    "Salesperson": (GLD["rep"], [("Salesperson", "salesperson_name"), ("Team", "team"), ("salesperson_key", "salesperson_key")]),
    "Sales": (GLD["sales"], [("Order Number", "order_number"), ("order_date_key", "order_date_key"), ("ship_date_key", "ship_date_key"),
                             ("customer_key", "customer_key"), ("product_key", "product_key"), ("warehouse_key", "warehouse_key"),
                             ("salesperson_key", "salesperson_key"), ("quantity", "quantity"), ("gross_amount", "gross_amount"),
                             ("discount_amount", "discount_amount"), ("net_amount", "net_amount"), ("cost_amount", "cost_amount")]),
    "Inventory": (GLD["inv"], [("snapshot_date_key", "snapshot_date_key"), ("product_key", "product_key"),
                               ("warehouse_key", "warehouse_key"), ("on_hand_qty", "on_hand_qty")]),
    "Budget": (GLD["bud"], [("month_date_key", "month_date_key"), ("Category", "category"), ("Region", "region"),
                            ("budget_amount", "budget_amount")]),
}
for tname, (gid, cols) in sem_map.items():
    gt = next(t for t in tables if t["id"] == gid)
    gcols = {c["name"]: c for c in gt["columns"]}
    out = []
    for friendly, src in cols:
        hidden = friendly == src  # snake_case = technical column, hidden from report authors
        key = "FK" if src.endswith("_key") and gt["kind"] == "fact" else ("SK" if src.endswith("_key") else None)
        out.append((friendly, gcols[src]["type"], key, "hidden" if hidden else ""))
    SEM[tname] = T("semantic", "Sales & Inventory", tname, "semantic-table", out, source_table=gid,
                   storage="Direct Lake", description=f"Direct Lake table over {gt['name']}.")
    for friendly, src in cols:
        E(f"{gid}.{src}", f"{SEM[tname]}.{friendly}", "rename" if friendly != src else "pass-through")
    # hidden flags
    t = next(x for x in tables if x["id"] == SEM[tname])
    for c in t["columns"]:
        if c.get("description") == "hidden":
            c["hidden"] = True
            del c["description"]

MEASURES = [
    ("Net Sales", "SUM ( Sales[net_amount] )", ["Sales.net_amount"], "Currency"),
    ("Gross Sales", "SUM ( Sales[gross_amount] )", ["Sales.gross_amount"], "Currency"),
    ("Discount", "SUM ( Sales[discount_amount] )", ["Sales.discount_amount"], "Currency"),
    ("Units", "SUM ( Sales[quantity] )", ["Sales.quantity"], "Volume"),
    ("Cost", "SUM ( Sales[cost_amount] )", ["Sales.cost_amount"], "Currency"),
    ("Gross Margin", "[Net Sales] - [Cost]", ["m:Net Sales", "m:Cost"], "Currency"),
    ("Margin %", "DIVIDE ( [Gross Margin], [Net Sales] )", ["m:Gross Margin", "m:Net Sales"], "Ratio"),
    ("Net Sales PY", "CALCULATE ( [Net Sales], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )", ["m:Net Sales", "Date.Date"], "Time intelligence"),
    ("YoY %", "DIVIDE ( [Net Sales] - [Net Sales PY], [Net Sales PY] )", ["m:Net Sales", "m:Net Sales PY"], "Time intelligence"),
    ("Sales by Ship Date", "CALCULATE ( [Net Sales], USERELATIONSHIP ( Sales[ship_date_key], 'Date'[date_key] ) )",
     ["m:Net Sales", "Sales.ship_date_key", "Date.date_key"], "Role-playing"),
    ("On Hand Units", "CALCULATE ( SUM ( Inventory[on_hand_qty] ), LASTNONBLANK ( 'Date'[Date], CALCULATE ( SUM ( Inventory[on_hand_qty] ) ) ) )",
     ["Inventory.on_hand_qty", "Date.Date"], "Semi-additive"),
    ("Budget", "SUM ( Budget[budget_amount] )", ["Budget.budget_amount"], "Plan"),
    ("Budget Variance", "[Net Sales] - [Budget]", ["m:Net Sales", "m:Budget"], "Plan"),
]
MID = T("semantic", "Sales & Inventory", "Measures", "measure-table",
        [(m[0], "measure", None, m[3]) for m in MEASURES], storage="Measures only",
        description="Display-only table that holds every measure, grouped by display folder.")
mt = next(x for x in tables if x["id"] == MID)
for c, m in zip(mt["columns"], MEASURES):
    c["expression"] = m[1]
    c["folder"] = m[3]
    c.pop("description", None)
    c["isMeasure"] = True
for name, expr, deps, folder in MEASURES:
    for d in deps:
        src = f"{MID}.{d[2:]}" if d.startswith("m:") else f"semantic.{d.split('.')[0]}.{d.split('.')[1]}"
        E(src, f"{MID}.{name}", "DAX")

# ------------------------------------------------------------------ reports
REPORTS = [
    ("Sales Overview", [
        ("KPI cards", ["Net Sales", "Margin %", "YoY %"], []),
        ("Monthly trend", ["Net Sales", "Net Sales PY"], ["Date.Month"]),
        ("Sales by category", ["Net Sales", "Gross Margin"], ["Product.Category"]),
        ("Budget vs actual", ["Net Sales", "Budget", "Budget Variance"], ["Product.Category", "Date.Month"]),
        ("Shipped vs ordered", ["Net Sales", "Sales by Ship Date"], ["Date.Month"]),
        ("Top customers", ["Net Sales", "Units"], ["Customer.Customer", "Customer.Segment"]),
    ]),
    ("Inventory Health", [
        ("On hand by warehouse", ["On Hand Units"], ["Warehouse.Warehouse"]),
        ("On hand vs units sold", ["On Hand Units", "Units"], ["Product.Category", "Date.Month"]),
    ]),
]
REP = {}
for rname, visuals in REPORTS:
    REP[rname] = T("report", rname, rname, "report",
                   [(v[0], "visual", None, ", ".join(v[1] + [f.split('.')[1] for f in v[2]])) for v in visuals],
                   description=f"Report: {rname}.")
    for vname, ms, fields in visuals:
        for m in ms:
            E(f"{MID}.{m}", f"{REP[rname]}.{vname}", "measure")
        for f in fields:
            E(f"semantic.{f.split('.')[0]}.{f.split('.')[1]}", f"{REP[rname]}.{vname}", "axis / filter")

# ------------------------------------------------------------ relationships
RELS = [
    # semantic-model relationships (also the gold FK -> PK constraints)
    {"fact": "Sales", "from": "order_date_key", "dim": "Date", "to": "date_key", "cardinality": "*:1", "active": True, "role": "Order date"},
    {"fact": "Sales", "from": "ship_date_key", "dim": "Date", "to": "date_key", "cardinality": "*:1", "active": False, "role": "Ship date"},
    {"fact": "Sales", "from": "customer_key", "dim": "Customer", "to": "customer_key", "cardinality": "*:1", "active": True},
    {"fact": "Sales", "from": "product_key", "dim": "Product", "to": "product_key", "cardinality": "*:1", "active": True},
    {"fact": "Sales", "from": "warehouse_key", "dim": "Warehouse", "to": "warehouse_key", "cardinality": "*:1", "active": True},
    {"fact": "Sales", "from": "salesperson_key", "dim": "Salesperson", "to": "salesperson_key", "cardinality": "*:1", "active": True},
    {"fact": "Inventory", "from": "snapshot_date_key", "dim": "Date", "to": "date_key", "cardinality": "*:1", "active": True, "role": "Snapshot date"},
    {"fact": "Inventory", "from": "product_key", "dim": "Product", "to": "product_key", "cardinality": "*:1", "active": True},
    {"fact": "Inventory", "from": "warehouse_key", "dim": "Warehouse", "to": "warehouse_key", "cardinality": "*:1", "active": True},
    {"fact": "Budget", "from": "month_date_key", "dim": "Date", "to": "date_key", "cardinality": "*:1", "active": True, "role": "Budget month",
     "note": "Budget rows land on the first day of each month; month-level visuals only."},
    {"fact": "Budget", "from": "Category", "dim": "Product", "to": "Category", "cardinality": "*:*", "active": True, "crossFilter": "single (Product filters Budget)",
     "note": "Many-to-many on category: Budget is coarser than Product."},
    {"fact": "Budget", "from": "Region", "dim": "Customer", "to": "Region", "cardinality": "*:*", "active": False,
     "note": "Kept inactive; region exists in both Customer and Salesperson and the business hasn't chosen one."},
]

# -------------------------------------------------------- analytic engine
ENGINE = [
    {"id": "consume", "name": "Consumption", "items": ["Power BI reports", "Excel (Analyze in Excel)", "Notebooks via semantic link", "Copilot / agents"],
     "does": "Turns a visual or question into a DAX query.", "trace": "Visual 'Sales by category' asks for [Net Sales] and [Gross Margin] by Product[Category]."},
    {"id": "query", "name": "Query engine (DAX)", "items": ["Formula engine (single-threaded)", "Storage engine (multi-threaded, xmSQL)", "Measure evaluation, filter context"],
     "does": "Formula engine plans the DAX; storage engine scans compressed columns in parallel.", "trace": "FE resolves [Gross Margin] = [Net Sales] - [Cost]; SE runs one xmSQL scan grouping Sales by Product[Category]."},
    {"id": "semantic", "name": "Semantic engine (VertiPaq)", "items": ["Direct Lake", "Import", "DirectQuery", "Relationships, RLS, calc groups"],
     "does": "Holds columns in memory, dictionary-encoded; applies relationships and security.", "trace": "Direct Lake pages in Sales[net_amount], Sales[cost_amount], Sales[product_key] and Product[Category] on first touch (transcoding)."},
    {"id": "serve", "name": "Serving & SQL", "items": ["Warehouse (T-SQL, transactions)", "SQL analytics endpoint (read-only)", "Views, security"],
     "does": "Gives SQL access to the same Delta tables; owns the load procedures for gold.", "trace": "Not on the hot path for Direct Lake on OneLake; Direct Lake on SQL endpoint can fall back here as DirectQuery."},
    {"id": "compute", "name": "Transform compute", "items": ["Spark notebooks", "Warehouse stored procedures", "Dataflows Gen2", "Pipelines (orchestration)"],
     "does": "Builds silver and gold. Runs on a schedule, not at query time.", "trace": "Last night's load wrote new Parquet files for fact_sales; the model was reframed after the load."},
    {"id": "storage", "name": "Storage (OneLake)", "items": ["Delta Lake tables", "Parquet files (V-Order)", "Shortcuts", "Mirrored databases"],
     "does": "One copy of the data, open format, read by every engine above.", "trace": "Column chunks for net_amount and product_key are read from V-Ordered Parquet files."},
]

# -------------------------------------------------------- pipeline config (metadata-driven sample)
PIPELINE_CONFIG = [
    {"source_system": "erp", "source_object": "sales_order_header", "target": "bronze.erp_sales_order_header", "method": "shortcut", "load_type": "n/a", "watermark_column": None, "load_order": 10},
    {"source_system": "erp", "source_object": "sales_order_line", "target": "bronze.erp_sales_order_line", "method": "shortcut", "load_type": "n/a", "watermark_column": None, "load_order": 10},
    {"source_system": "erp", "source_object": "inventory_txn", "target": "bronze.erp_inventory_txn", "method": "copy", "load_type": "incremental", "watermark_column": "txn_id", "load_order": 10},
    {"source_system": "crm", "source_object": "salesperson", "target": "bronze.crm_salesperson", "method": "copy (REST)", "load_type": "full", "watermark_column": None, "load_order": 10},
    {"source_system": "files", "source_object": "budget/*.csv", "target": "bronze.files_budget", "method": "copy (file)", "load_type": "new files", "watermark_column": "_file_modified", "load_order": 10},
    {"source_system": "bronze", "source_object": "erp_sales_order_*", "target": "silver.sales_order_line", "method": "notebook", "load_type": "merge", "watermark_column": "_modified_at", "load_order": 20},
    {"source_system": "silver", "source_object": "customer", "target": "gold.dim_customer", "method": "stored procedure", "load_type": "scd2", "watermark_column": "_modified_at", "load_order": 30},
    {"source_system": "silver", "source_object": "sales_order_line", "target": "gold.fact_sales", "method": "stored procedure", "load_type": "delete-insert by date", "watermark_column": "_modified_at", "load_order": 40},
]

# ------------------------------------------------------------ hierarchies (semantic model)
HIERARCHIES = [
    {"table": "Date", "name": "Calendar", "levels": ["Fiscal Year", "Quarter", "Month", "Date"]},
    {"table": "Product", "name": "Product", "levels": ["Category", "Subcategory", "Product"]},
    {"table": "Customer", "name": "Geography", "levels": ["Region", "State", "City", "Customer"]},
    {"table": "Salesperson", "name": "Sales team", "levels": ["Team", "Salesperson"]},
]

model = {
    "$schema_note": "See model/index.html for the shape. Generated by tools/build_sample_model.py.",
    "model": {"name": "Sample order-to-cash & inventory model", "version": "1.0",
              "description": "Generic, invented model used by every exploration. Swap it for your own metadata."},
    "layers": LAYERS,
    "tables": tables,
    "columnLineage": col_edges,
    "relationships": RELS,
    "hierarchies": HIERARCHIES,
    "engine": ENGINE,
    "pipelineConfig": PIPELINE_CONFIG,
}

# sanity: every edge endpoint exists
ids = {f"{t['id']}.{c['name']}" for t in tables for c in t["columns"]}
bad = [e for e in col_edges if e["from"] not in ids or e["to"] not in ids]
if bad:
    raise SystemExit("Bad edges:\n" + "\n".join(f"{e['from']} -> {e['to']}" for e in bad))

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(model, indent=1))
print(f"wrote {OUT}: {len(tables)} tables, {sum(len(t['columns']) for t in tables)} columns, {len(col_edges)} column edges")
