FROM python:3.8

RUN mdkir /deploy-django-aws

WORKDIR /deploy-django-aws

RUN pip install --upgrade pip && \
    pip install --no-cache-dir boto3 && \
    pip install --no-cache-dir argparse

ADD python_cicd.py /deploy-django-aws

ADD entrypoint.sh /deploy-django-aws

RUN chmod +x ./entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
