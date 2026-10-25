FROM python:3.12-slim
RUN pip install --no-cache-dir flask pyyaml
RUN echo "FLAG{YAML_UNSAFE_LOAD_RCE}" > /opt/yaml_flag.txt
WORKDIR /app
COPY app.py .
EXPOSE 8080
CMD ["python3", "app.py"]
