import gzip
import json
import os

from google.cloud import storage
from google.cloud.exceptions import Conflict, GoogleCloudError


class ETL(object):

  def __init__(self, config):
    self.config = config
    self.path = self.config['local_path']

  @staticmethod
  def extract(filename):
    """Extract compressed json and return dict

    Args:
      filename: path to json.gz file

    Returns:
      nvd_dict: dict containing deserialized NVD data

    Raises:
      ValueError: when failing to open gzipped file
      TypeError: when failing to deserialize json when the serialized json is not string, bytes, or bytearray, or when the filename is an expexcted type
      json.JSONDecodeError: when failing to deserialize json due to serialized json containing an unexpected UTF-8 BOM
    """
    try:
      with gzip.open(filename, 'rb') as f:
        json_content = f.read()
    except ValueError as e:
      raise e
    except TypeError as e:
      raise TypeError('gzip.open failed in ETL.extract: ' + str(e))

    try:
      nvd_dict = json.loads(json_content)
    except json.JSONDecodeError as e:
      raise e
    except TypeError as e:
      raise TypeError('json.loads failed in ETL.extract: ' + str(e))

    return nvd_dict

  def transform(self, nvd_dict, filename, bq, deltas_only=False):
    """Transforms deserialized NVD data into newline delmited json for BQ import

    Args:
      nvd_dict: deserialized NVD data
      filename: the output filename

    Returns:
      local_file: absolute path of newline delimited json

    Raises:
      IOError: on failed write to json file
    """
    local_file = self.path + filename + '_newline.json'

    # We can discard the metadata contained in the CVE_data* keys.
    # CVE_Items has what we want.
    cve_list = nvd_dict['CVE_Items']
    scrubbed_list = []

    if deltas_only:
      cveids = bq.get_cve_ids(self.config['dataset'])
      for cve in cve_list:
        if cve['cve']['CVE_data_meta']['ID'] not in cveids:
          scrubbed_list.append(cve)
    else:
      scrubbed_list = cve_list
    try:
      for cve in scrubbed_list:
        with open(local_file, 'a') as f:
          f.write(json.dumps(cve, indent=None, separators=(',', ':')) + '\n')
    except IOError as e:
      raise IOError('newline delimited json serialization failed in '
                    'ETL.transform: ' + str(e))

    return local_file

  def load(self, filename, bucket_name):
    """Load the NVD data into BQ by way of a GCS bulk load

    Args:
      filename: the newline delimited json file
      bucket_name: the bucket we'll put the file into

    Returns:
      None

    Raises:
      GoogleCloudError: if there's an issue with uploading to GCS
    """
    storage_client = storage.Client()
    try:
      bucket = storage_client.create_bucket(bucket_name)
    except Conflict as e:
      # the bucket already exists, and that's ok
      bucket = storage_client.get_bucket(bucket_name)

    try:
      blob = bucket.blob(os.path.basename(filename))
      blob.upload_from_filename(filename)
    except GoogleCloudError as e:
      raise e

    self.bq_load_from_gcs(self.config['dataset'], blob)

  def bq_load_from_gcs(self, dataset, blob):
    pass