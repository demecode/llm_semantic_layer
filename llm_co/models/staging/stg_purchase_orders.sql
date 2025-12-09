with source as (
    select * from {{ source('raw', 'purchase_orders') }}
),

typed as (
    select
        po_number,
        cast(po_item_number as int)        as po_item_number,
        cast(po_version as int)            as po_version,
        order_type,
        cast(value_in_doc_currency as double) as value_in_doc_currency,
        document_currency,
        cast(value_in_gbp as double)       as value_in_gbp,
        profit_centre,
        project_number,
        project_description,
        material,
        material_description,
        product,
        product_variant,
        ipt,
        vendor_name,
        vendor_number,
        vendor_classification,
        vendor_macro_category,
        vendor_micro_category,
        plant,
        site,
        sector,
        sector_description,
        line_of_business,
        line_of_business_description,
        division,
        division_description,
        buyer_code,
        created_by,
        cast(po_creation_date as date)         as po_creation_date,
        cast(po_sent_to_vendor_date as date)   as po_sent_to_vendor_date,
        cast(acknowledgement_date as date)     as acknowledgement_date,
        acknowledgement_text,
        acknowledgement_category,
        cast(promise_date as date)             as promise_date,
        cast(ois_qty as double)                as ois_qty,
        cast(ois_goods_received_qty as double) as ois_goods_received_qty,
        cast(ois_outstanding_qty as double)    as ois_outstanding_qty,
        cast(oi_total_invoiced_document_currency as double)
            as oi_total_invoiced_document_currency,
        cast(oi_total_invoiced_gbp as double)  as oi_total_invoiced_gbp,
        cast(ois_value_document_currency as double)
            as ois_value_document_currency,
        cast(ois_value_gbp as double)          as ois_value_gbp,
        cast(order_on_hold as boolean)         as order_on_hold,
        good_or_bad,
        cast(po_ack as boolean)                as po_ack
    from source
)

select * from typed;