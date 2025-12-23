with base as (
    select
        po_number,
        po_item_number,
        line_of_business,
        division,
        vendor_name,
        vendor_macro_category,
        vendor_micro_category,
        po_creation_date,
        date_trunc('month', po_creation_date) as month,
        value_in_gbp,
        ois_qty,
        ois_goods_received_qty,
        ois_outstanding_qty,
        oi_total_invoiced_gbp
    from {{ ref('stg_purchase_orders') }}
)

select * from base;