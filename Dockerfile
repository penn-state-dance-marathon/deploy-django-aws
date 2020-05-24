FROM python:3

RUN pip install --upgrade pip && \
    pip install --no-cache-dir boto3 && \
    pip install --no-cache-dir argparse

ADD python_cicd.py /

ENTRYPOINT ["python", "python_cicd.py", "$INPUT_APPLICATION", "$INPUT_ENVIRONMENT"]
