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
  """Driver clas for BigQuery National Vulnerability Database (BQ-NVD)."""

  def __init__(self):
    """Init BQNVD class with config values and initialize module objects."""

    # Get config values from OS environment variables, if they don't exist,
    # load them from yaml config file.
    # Note: this is to support local running or GKE.
    self.config = {}
    load_from_yaml = False
    var_names = ['local_path',
                 'bucket_name',
                 'project',
                 'dataset',
                 'nvd_schema',
                 'url_base',
                 'file_prefix',
                 'file_suffix']
    for var in var_names:
      if os.environ.get(var):
        self.config[var] = os.environ.get(var)
      else:
        load_from_yaml = True

    if load_from_yaml:
      with open('./config.yml', 'r') as f:
        try:
          self.config = yaml.safe_load(f)
        except yaml.YAMLError as e:
          self.print_error_and_exit('yaml config load failed', str(e), 1)

    # Initialize our download, ETL, and BQ objects
    self.d = Download(self.config)
    self.etl = ETL(self.config)
    try:
      self.bq = BQ(self.config)
    except DefaultCredentialsError as e:
      self.print_error_and_exit('error initializing BQ client: ', str(e), 1)

  @staticmethod
  def print_debug(message):
    """Print debug messages to stdout in expectation of Stackdriver getting
    container logs from GKE."""
    print('+++ bq-ndv.py debug: ' + message)

  @staticmethod
  def print_error_and_exit(message, exception, signal):
    """Helper funciton to print stack trace and exit 1"""
    print(message + ': ' + str(exception))
    traceback.print_exc(file=sys.stdout)
    sys.exit(signal)

  def check_bootstrap(self):
    """Determine if we're in a greenfield or brownfield environment."""
    dataset = self.config['dataset']
    try:
      cve_count = self.bq.count_cves(dataset)
    except TypeError as e:
      self.print_error_and_exit('count_cves failed on dataset ' + dataset, e, 1)

    # There are over 130k CVEs in the NVD, so if it looks like there aren't
    # enough, either we've never bootstrapped or something's gone wrong. So
    # either way, we'll bootstrap.
    if cve_count < 130000:
      self.bootstrap()
      return True
    else:
      return False

  def bootstrap(self):
    """Process the entirety of NVD."""
    self.print_debug('bootstrapping')
    current_year = datetime.now().year

    for year in range(2002, current_year + 1):
      downloaded_filename = self.download(str(year))
      nvd_dict = self.extract(downloaded_filename)
      transformed_local_filename = self.transform(nvd_dict, downloaded_filename)
      self.load(transformed_local_filename)

  def incremental(self):
    """Do an incremental update."""
    self.print_debug('doing incremental update')
    downloaded_filename = self.download('recent')
    nvd_dict = self.extract(downloaded_filename)
    transformed_local_filename = self.transform(nvd_dict, downloaded_filename)
    self.load(transformed_local_filename)

  def download(self, name):
    """Step 1 - Download the NVD json feed."""
    self.print_debug('downloading ' + name)
    try:
      local_path = self.config['local_path']
      downloaded_filename = self.d.download(name, local_path)
    except ContentTooShortError as e:
      self.print_error_and_exit('download failed', e, 1)
    return downloaded_filename

  def extract(self, downloaded_filename):
    """Step 2 - Decompress tar.gz json data and return a dict."""
    self.print_debug('extracting ' + downloaded_filename)
    try:
      nvd_dict = self.etl.extract(downloaded_filename)
    except (ValueError, TypeError, JSONDecodeError) as e:
      self.print_error_and_exit('extraction failed for ' + downloaded_filename,
                                e, 1)
    return nvd_dict

  def transform(self, nvd_dict, downloaded_filename):
    """Step 3 - Transform the dict into newline delimited json."""
    self.print_debug('transforming nvd_data')
    try:
      transformed_local_filename = self.etl.transform(nvd_dict,
                                                      os.path.basename(
                                                          downloaded_filename),
                                                      self.bq)
    except IOError as e:
      self.print_error_and_exit('extraction failed for ' + downloaded_filename, e, 1)

    return transformed_local_filename

  def load(self, transformed_local_filename):
    """Step 4 - Load the json into GCS and import to BQ."""
    if transformed_local_filename is None:
      self.print_debug('no updates to load')
      return

    self.print_debug('loading ' + transformed_local_filename)
    try:
      bucket_name = self.config['bucket_name']
      self.etl.load(self.bq, transformed_local_filename, bucket_name)
    except (Conflict, GoogleCloudError) as e:
      self.print_error_and_exit('load failed for ' + transformed_local_filename, e, 1)


def main():
  """Process is:
    Step 1 - Download from NVD json feeds.
    Step 2 - Decompress tar.gz json data and return a dict.
    Step 3 - Transform the dict into newline delimited json.
    Step 4 - Load the json into GCS and import to BQ.
  """
  bqnvd = BQNVD()

  if not bqnvd.check_bootstrap():
    bqnvd.incremental()

if __name__ == '__main__':
  main()
