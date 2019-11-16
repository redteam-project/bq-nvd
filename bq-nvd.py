import os
import yaml
import sys
import traceback
from datetime import datetime
from json import JSONDecodeError
from urllib.error import ContentTooShortError

from google.auth.exceptions import DefaultCredentialsError
from google.cloud.exceptions import Conflict, GoogleCloudError

from bq_nvd.bq import BQ
from bq_nvd.download import Download
from bq_nvd.etl import ETL


class BQNVD(object):

  def __init__(self):
    with open('./config.yml', 'r') as f:
      try:
        self.config = yaml.safe_load(f)
      except yaml.YAMLError as e:
        self.print_error_and_exit('yaml config load failed', str(e), 1)
    self.d = Download()
    self.etl = ETL(self.config)
    try:
      self.bq = BQ(self.config)
    except DefaultCredentialsError as e:
      self.print_error_and_exit('error initializing BQ client: ', str(e), 1)

  @staticmethod
  def print_debug(message):
    print('+++ bq-ndv.py debug: ' + message)

  @staticmethod
  def print_error_and_exit(message, exception, signal):
    print(message + ': ' + str(exception))
    traceback.print_exc(file=sys.stdout)
    sys.exit(signal)

  def bootstrap(self):
    self.print_debug('bootstrapping')
    current_year = datetime.now().year
    for year in range(2002, current_year + 1):
      downloaded_filename = self.download(str(year))
      transformed_local_filename = self.transform(downloaded_filename)
      self.load(transformed_local_filename)

  def download(self, name):
    self.print_debug('downloading ' + name)
    try:
      downloaded_filename = self.d.download(name, self.config['local_path'])
    except ContentTooShortError as e:
      self.print_error_and_exit('download failed', e, 1)
    return downloaded_filename

  def check_bootstrap(self):
    dataset = self.config['dataset']
    try:
      cve_count = self.bq.count_cves(dataset)
    except TypeError as e:
      self.print_error_and_exit('count_cves failed on dataset ' + dataset, e, 1)

    if cve_count == 0:
      self.bootstrap()
      return True
    else:
      return False

  def transform(self, downloaded_filename, deltas_only=False):
    self.print_debug('transforming ' + downloaded_filename)
    try:
      nvd_data = self.etl.extract(downloaded_filename)
      transformed_local_filename = self.etl.transform(nvd_data,
                                                      os.path.basename(
                                                          downloaded_filename),
                                                      self.bq,
                                                      deltas_only)
    except (ValueError, TypeError, JSONDecodeError) as e:
      self.print_error_and_exit('extraction failed for ' + downloaded_filename, e, 1)

    return transformed_local_filename

  def load(self, transformed_local_filename):
    self.print_debug('loading ' + transformed_local_filename)
    try:
      self.etl.load(self.bq, transformed_local_filename, self.config['bucket_name'])
    except (Conflict, GoogleCloudError) as e:
      self.print_error_and_exit('load failed for ' + transformed_local_filename, e, 1)

  def incremental(self):
    local_path = self.config['local_path']
    bucket_name = self.config['bucket_name']

    downloaded_filename = self.download('recent')
    transformed_local_filename = self.transform(downloaded_filename,
                                                deltas_only=True)
    self.load(transformed_local_filename)

def main():
  bqnvd = BQNVD()
  if not bqnvd.check_bootstrap():
    bqnvd.incremental()

if __name__ == '__main__':
  main()
