FROM python:3

RUN pip install --upgrade pip && \
    pip install --no-cache-dir boto3 && \
    pip install --no-cache-dir argparse

COPY entrypoint.sh /entrypoint.sh
COPY python_cicd.py /python_cicd.py

ENTRYPOINT ["python", "python_cicd.py", "$1", "$2"]
