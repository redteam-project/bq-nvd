FROM python:3.8
COPY . /usr/local/bq_nvd
WORKDIR /usr/local/bq_nvd
RUN python3 -m pip install -r requirements.txt
ENTRYPOINT ["python3", "/usr/local/bq_nvd/bq-nvd.py"]
