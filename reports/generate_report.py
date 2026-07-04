import os
import textwrap
import warnings
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import psycopg2

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "output", "energy_report.pdf")


def _connect():
    return psycopg2.connect(
        host=os.environ.get("DBT_POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("DBT_POSTGRES_PORT", "5432")),
        user=os.environ.get("DBT_POSTGRES_USER", "dakota_user"),
        password=os.environ.get("DBT_POSTGRES_PASSWORD", "change_me"),
        dbname=os.environ.get("DBT_POSTGRES_DB", "energy_analytics"),
    )


def load_data(conn):
    imports_monthly = pd.read_sql(
        "select * from gold.fct_natural_gas_imports_monthly order by period_month", conn
    )
    weather_monthly = pd.read_sql(
        "select * from gold.fct_national_weather_monthly order by period_month", conn
    )
    weather_daily = pd.read_sql(
        "select * from gold.fct_weather_daily order by observation_date", conn
    )
    return imports_monthly, weather_monthly, weather_daily


def build_report(imports_monthly, weather_monthly, weather_daily):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    us_total = (
        imports_monthly[imports_monthly["area_name"] == "U.S."]
        .groupby("period_month")["total_import_volume_mmcf"]
        .sum()
    )
    latest_month = imports_monthly["period_month"].max()
    latest_countries = (
        imports_monthly[
            (imports_monthly["period_month"] == latest_month) & (imports_monthly["area_name"] != "U.S.")
        ]
        .groupby("area_name")["total_import_volume_mmcf"]
        .sum()
        .pipe(lambda s: s[s > 0])
        .sort_values(ascending=False)
        .head(8)
    )

    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(OUTPUT_PATH) as pdf:
        # Page 1: summary + headline numbers
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.08, 0.94, "Dakota Energy Analytics — Executive Report", fontsize=18, fontweight="bold")
        fig.text(0.08, 0.91, f"Generated {generated_at}", fontsize=9, color="#555555")

        latest_volume = us_total.iloc[-1] if len(us_total) else float("nan")
        prior_volume = us_total.iloc[-2] if len(us_total) > 1 else None
        change_txt = ""
        if prior_volume:
            pct = (latest_volume - prior_volume) / prior_volume * 100
            change_txt = f"  ({pct:+.1f}% vs prior month)"

        summary_lines = [
            f"Latest month covered: {latest_month}",
            f"U.S. total natural gas imports (latest month): {latest_volume:,.0f} MMCF{change_txt}",
            f"Months of import history: {imports_monthly['period_month'].nunique()}",
        ]
        if len(weather_monthly):
            latest_w = weather_monthly.iloc[-1]
            summary_lines.append(
                f"National avg temperature (latest month on record): {latest_w['avg_temperature_f']:.1f}°F, "
                f"heating degree hours: {latest_w['total_heating_degree_hours']:.0f}, "
                f"cooling degree hours: {latest_w['total_cooling_degree_hours']:.0f}"
            )
        else:
            summary_lines.append("No weather data collected yet.")

        wrapped = "\n".join(
            textwrap.fill(f"•  {line}", width=88, subsequent_indent="   ") for line in summary_lines
        )
        fig.text(0.08, 0.85, wrapped, fontsize=11, va="top")
        pdf.savefig(fig)
        plt.close(fig)

        # Page 2: US import volume trend
        fig, ax = plt.subplots(figsize=(8.5, 5.5))
        us_total.plot(ax=ax, marker="o", color="#1f77b4")
        ax.set_title("U.S. Total Natural Gas Import Volume by Month")
        ax.set_xlabel("Month")
        ax.set_ylabel("Volume (MMCF)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # Page 3: top source countries, latest month. Log scale -- pipeline imports from
        # Canada are roughly two orders of magnitude larger than most LNG source countries,
        # so a linear scale would make everything but Canada invisible.
        if len(latest_countries):
            fig, ax = plt.subplots(figsize=(8.5, 5.5))
            bars = ax.barh(latest_countries.index, latest_countries.values, color="#2ca02c")
            ax.set_xscale("log")
            ax.set_title(f"Top Import Source Countries — {latest_month} (log scale)")
            ax.set_xlabel("Volume (MMCF)")
            ax.invert_yaxis()
            ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=3)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        # Page 4: weather trend, if we have enough data to plot
        if len(weather_daily):
            fig, ax = plt.subplots(figsize=(8.5, 5.5))
            for region, group in weather_daily.groupby("region_code"):
                ax.plot(group["observation_date"], group["avg_temperature_f"], marker="o", label=region)
            ax.set_title("Daily Average Temperature by Region")
            ax.set_xlabel("Date")
            ax.set_ylabel("Avg Temperature (°F)")
            span = weather_daily["observation_date"].max() - weather_daily["observation_date"].min()
            pad = timedelta(days=max(2, span.days // 4 or 2))
            ax.set_xlim(weather_daily["observation_date"].min() - pad, weather_daily["observation_date"].max() + pad)
            ax.legend(fontsize=7, ncol=2)
            ax.grid(alpha=0.3)
            fig.autofmt_xdate()
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    print(f"wrote {OUTPUT_PATH}")


def main():
    conn = _connect()
    try:
        imports_monthly, weather_monthly, weather_daily = load_data(conn)
    finally:
        conn.close()
    build_report(imports_monthly, weather_monthly, weather_daily)


if __name__ == "__main__":
    main()
