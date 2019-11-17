FROM marketplace.gcr.io/google/debian9
RUN apt-get update && \
    apt-get install -y python3 python3-pip
COPY . /usr/local/bq_nvd
WORKDIR /usr/local/bq_nvd
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3", "/usr/local/bq_nvd/bq-nvd.py"]
