select
    series,
    to_date(period || '-01', 'YYYY-MM-DD') as period_month,
    duoarea,
    area_name,
    product,
    product_name,
    process,
    process_name,
    series_description,
    value,
    units,
    ingested_at
from {{ source('bronze', 'eia_natural_gas_imports') }}
