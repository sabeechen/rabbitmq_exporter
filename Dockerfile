FROM python:3.10.12-slim-buster
LABEL org.opencontainers.image.source="https://github.com/sabeechen/rabbitmq_exporter"
COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt
COPY exporter.py /exporter.py
CMD ["python", "/exporter.py"]
