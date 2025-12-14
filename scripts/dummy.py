import random
from datetime import datetime, timedelta
from faker import Faker
import pandas as pd

fake = Faker("en_GB")

CURRENCIES = ["GBP", "EUR", "USD"]
FX_RATES = {
    "GBP": 1.0,
    "EUR": 0.85,
    "USD": 0.78,
}

ORDER_TYPES = ["STANDARD", "SERVICE", "RETURN"]
VENDOR_CLASSIFICATIONS = ["Strategic", "Preferred", "Approved", "Tactical"]
VENDOR_MACRO = ["IT", "Marketing", "Logistics", "Facilities", "HR", "Consulting"]
VENDOR_MICRO = {
    "IT": ["Cloud Services", "Software Licences", "Hardware", "Support"],
    "Marketing": ["Digital Ads", "Print", "Events"],
    "Logistics": ["Courier", "Freight", "Warehousing"],
    "Facilities": ["Cleaning", "Security", "Maintenance"],
    "HR": ["Recruitment", "Training"],
    "Consulting": ["Strategy", "Technology", "Operations"],
}
SECTORS = ["Public", "Private", "Internal"]
LINES_OF_BUSINESS = ["Digital Solutions", "Retail", "Corporate", "Operations"]
DIVISIONS = ["UK", "EMEA", "Global"]

ACK_CATEGORIES = ["On-Time", "Late", "Rejected", "Amended", "Pending"]

PRODUCTS = ["SaaS Platform", "Consulting", "Support", "Hardware", "Implementation"]
VARIANTS = ["Basic", "Standard", "Premium", "Enterprise"]

def random_date_between(start_days_ago=365, end_days_ago=0):
    """Return a random datetime between now - start_days_ago and now - end_days_ago."""
    now = datetime.now()
    start = now - timedelta(days=start_days_ago)
    end = now - timedelta(days=end_days_ago)
    return fake.date_between_dates(date_start=start.date(), date_end=end.date())

def generate_row(po_number: str, po_item_number: int):
    # Choose currency and FX
    doc_currency = random.choice(CURRENCIES)
    fx = FX_RATES[doc_currency]

    # Generate a base value
    value_doc = round(random.uniform(500, 50000), 2)
    value_gbp = round(value_doc * fx, 2)

    # Quantities
    ois_qty = round(random.uniform(1, 100), 2)
    received_qty = round(random.uniform(0, ois_qty), 2)
    outstanding_qty = round(ois_qty - received_qty, 2)

    # Invoiced values (could be partial)
    invoiced_ratio = random.uniform(0, 1.1)  # can go slightly over
    oi_total_inv_doc = round(value_doc * invoiced_ratio, 2)
    oi_total_inv_gbp = round(oi_total_inv_doc * fx, 2)

    # OIS value (open item schedule/promised)
    ois_value_doc = round(value_doc * (ois_qty / max(ois_qty, 1)), 2)  # simplistic
    ois_value_gbp = round(ois_value_doc * fx, 2)

    # Vendor classification & categories
    vendor_macro = random.choice(VENDOR_MACRO)
    vendor_micro = random.choice(VENDOR_MICRO[vendor_macro])

    # Org structure
    sector = random.choice(SECTORS)
    lob = random.choice(LINES_OF_BUSINESS)
    division = random.choice(DIVISIONS)

    # Dates: ensure ordering
    po_creation_date = random_date_between(365, 60)   # up to a year old
    po_sent_to_vendor_date = po_creation_date + timedelta(days=random.randint(0, 5))

    # Acknowledgement may or may not exist
    has_ack = random.random() < 0.8  # 80% acknowledged
    acknowledgement_date = None
    acknowledgement_text = None
    acknowledgement_category = None
    po_ack = has_ack

    if has_ack:
        acknowledgement_date = po_sent_to_vendor_date + timedelta(days=random.randint(0, 10))
        acknowledgement_category = random.choice(ACK_CATEGORIES)
        acknowledgement_text = f"Vendor acknowledged as {acknowledgement_category}"

    # Promise date (delivery)
    promise_date = (acknowledgement_date or po_sent_to_vendor_date) + timedelta(days=random.randint(1, 60))

    # Classification good/bad (toy logic)
    # e.g. BAD if outstanding_qty is high or acknowledgement is Late/Rejected
    if outstanding_qty > 0.5 * ois_qty or acknowledgement_category in ["Late", "Rejected"]:
        good_or_bad = "BAD"
    else:
        good_or_bad = "GOOD"

    # Misc fields
    profit_centre = f"PC{random.randint(100, 999)}"
    project_number = f"PRJ-{random.randint(1000, 9999)}"
    project_description = f"Project {project_number} - {lob}"
    material = f"MAT-{random.randint(10000, 99999)}"
    material_description = f"{random.choice(PRODUCTS)} {random.choice(VARIANTS)}"
    product = random.choice(PRODUCTS)
    product_variant = random.choice(VARIANTS)
    ipt = f"IPT-{random.randint(1, 20)}"

    vendor_number = f"V{random.randint(10000, 99999)}"
    vendor_name = f"{fake.company()} {vendor_macro}"
    plant = f"PLANT-{random.randint(1, 10)}"
    site = fake.city()

    sector_description = f"{sector} sector"
    lob_description = f"{lob} line of business"
    division_description = f"{division} division"

    buyer_code = f"BUY{random.randint(100, 999)}"
    created_by = fake.user_name()

    order_on_hold = random.random() < 0.05  # 5% on hold

    # Single row as dict
    return {
        "po_number": po_number,
        "po_item_number": po_item_number,
        "po_version": random.randint(1, 3),
        "order_type": random.choice(ORDER_TYPES),
        "value_in_doc_currency": value_doc,
        "document_currency": doc_currency,
        "value_in_gbp": value_gbp,
        "profit_centre": profit_centre,
        "project_number": project_number,
        "project_description": project_description,
        "material": material,
        "material_description": material_description,
        "product": product,
        "product_variant": product_variant,
        "ipt": ipt,
        "vendor_name": vendor_name,
        "vendor_number": vendor_number,
        "vendor_classification": random.choice(VENDOR_CLASSIFICATIONS),
        "vendor_macro_category": vendor_macro,
        "vendor_micro_category": vendor_micro,
        "plant": plant,
        "site": site,
        "sector": sector,
        "sector_description": sector_description,
        "line_of_business": lob,
        "line_of_business_description": lob_description,
        "division": division,
        "division_description": division_description,
        "buyer_code": buyer_code,
        "created_by": created_by,
        "po_creation_date": po_creation_date,
        "po_sent_to_vendor_date": po_sent_to_vendor_date,
        "acknowledgement_date": acknowledgement_date,
        "acknowledgement_text": acknowledgement_text,
        "acknowledgement_category": acknowledgement_category,
        "promise_date": promise_date,
        "ois_qty": ois_qty,
        "ois_goods_received_qty": received_qty,
        "ois_outstanding_qty": outstanding_qty,
        "oi_total_invoiced_document_currency": oi_total_inv_doc,
        "oi_total_invoiced_gbp": oi_total_inv_gbp,
        "ois_value_document_currency": ois_value_doc,
        "ois_value_gbp": ois_value_gbp,
        "order_on_hold": order_on_hold,
        "good_or_bad": good_or_bad,
        "po_ack": po_ack,
    }

def generate_dataset(n_pos: int = 5000, max_items_per_po: int = 5) -> pd.DataFrame:
    rows = []
    for _ in range(n_pos):
        po_number = str(fake.random_number(digits=10, fix_len=True))
        items = random.randint(1, max_items_per_po)
        for item_idx in range(1, items + 1):
            row = generate_row(po_number, item_idx)
            rows.append(row)
    return pd.DataFrame(rows)

if __name__ == "__main__":
    df = generate_dataset(n_pos=2000, max_items_per_po=5)
    df.to_csv("purchase_orders.csv", index=False)
    print("Generated purchase_orders.csv with", len(df), "rows")