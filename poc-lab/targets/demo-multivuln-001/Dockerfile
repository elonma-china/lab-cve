FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask
RUN mkdir -p /opt && \
    echo "FLAG{CMDI_PING_RCE}" > /opt/secret_cmdi.txt && \
    echo "FLAG{PATH_TRAVERSAL_DOWNLOAD}" > /opt/secret_traversal.txt
WORKDIR /app
COPY app.py .
COPY files/ ./files/
EXPOSE 8080
CMD ["python3", "app.py"]
