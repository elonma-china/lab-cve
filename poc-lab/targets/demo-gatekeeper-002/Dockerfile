FROM python:3.12-slim
RUN pip install --no-cache-dir flask requests
RUN echo "FLAG{SSTI_JINJA_BLACKLIST_BYPASS}" > /opt/ssti_flag.txt && \
    echo "FLAG{PICKLE_PREFS_RCE}" > /opt/pickle_flag.txt
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python3", "app.py"]
