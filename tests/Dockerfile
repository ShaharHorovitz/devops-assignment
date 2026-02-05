# Test image - runs integration tests against the nginx container
FROM python:3-alpine

RUN pip install --no-cache-dir requests

COPY test_nginx.py /app/test_nginx.py
WORKDIR /app

ENTRYPOINT ["python", "test_nginx.py"]
