FROM quay.io/astronomer/astro-runtime:3.0-16-python-3.12-base

COPY orchestration/requirements.txt /usr/local/airflow/requirements.txt
RUN pip install --no-cache-dir -r /usr/local/airflow/requirements.txt

COPY ingestion /usr/local/airflow/ingestion
RUN pip install --no-cache-dir /usr/local/airflow/ingestion
