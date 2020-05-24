FROM python:3.8

WORKDIR /deploy-django-aws

RUN pip install --upgrade pip && \
    pip install --no-cache-dir boto3 && \
    pip install --no-cache-dir argparse

COPY entrypoint.sh /entrypoint.sh

COPY python_cicd.py /python_cicd.py

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
