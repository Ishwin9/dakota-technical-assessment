"""Reference metadata for the electric grid regions this service knows how to enrich.

Codes mirror EIA-930 balancing-authority codes (electricity/rto/region-data) so
enrichment records can be joined 1:1 against ingested EIA demand data on region_code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionProfile:
    code: str
    name: str
    timezone: str
    climate_zone: str
    base_temp_f: float  # rough annual-average temperature used to seed synthetic weather
    temp_swing_f: float  # amplitude of daily/seasonal variation


REGIONS: dict[str, RegionProfile] = {
    "CISO": RegionProfile("CISO", "California ISO", "America/Los_Angeles", "mediterranean", 62.0, 18.0),
    "ERCO": RegionProfile("ERCO", "Electric Reliability Council of Texas", "America/Chicago", "humid_subtropical", 70.0, 22.0),
    "PJM": RegionProfile("PJM", "PJM Interconnection", "America/New_York", "humid_continental", 55.0, 25.0),
    "MISO": RegionProfile("MISO", "Midcontinent ISO", "America/Chicago", "humid_continental", 52.0, 28.0),
    "SWPP": RegionProfile("SWPP", "Southwest Power Pool", "America/Chicago", "semi_arid", 58.0, 26.0),
    "NYIS": RegionProfile("NYIS", "New York ISO", "America/New_York", "humid_continental", 50.0, 24.0),
    "ISNE": RegionProfile("ISNE", "ISO New England", "America/New_York", "humid_continental", 48.0, 23.0),
    "SOCO": RegionProfile("SOCO", "Southern Company", "America/New_York", "humid_subtropical", 66.0, 18.0),
}

DEFAULT_REGION_CODES = list(REGIONS.keys())
