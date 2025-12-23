{{ config(materialized='table') }}

with spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="to_date('2020-01-01')",
        end_date="dateadd(day, 1, current_date)"
    ) }}

)

select
  cast(date_day as date) as date_day
from spine