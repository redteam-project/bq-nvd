FROM python:3.8
COPY . /usr/local/bq_nvd
WORKDIR /usr/local/bq_nvd
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3", "/usr/local/bq_nvd/bq-nvd.py"]
