FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r -u 10002 relay \
    && mkdir -p /app/loot \
    && chown -R relay:relay /app
USER relay
EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:app"]
