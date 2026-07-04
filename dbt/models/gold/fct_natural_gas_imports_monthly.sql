select
    period_month,
    area_name,
    sum(value) as total_import_volume_mmcf
from {{ ref('stg_eia_natural_gas_imports') }}
where units = 'MMCF'
group by 1, 2
