import gzip
import json
import os

from google.cloud import storage
from google.cloud.exceptions import Conflict, GoogleCloudError


class ETL(object):
  """Extract / Transform / Load object.

  Attributes:
    config: configuration data
  """

  def __init__(self, config):
    """Initialize ETL object with config data."""
    self.config = config

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
      nvd_dict = json.loads(json_content.decode('utf-8'))
    except json.JSONDecodeError as e:
      raise e
    except TypeError as e:
      raise TypeError('json.loads failed in ETL.extract: ' + str(e))

    return nvd_dict

  def transform(self, nvd_dict, filename, bq, deltas_only=True):
    """Transforms deserialized NVD data into newline delmited json for BQ
    import. The default is to transform only CVEs that do not already exist
    in the BQ dataset, but if you want to disable that, set deltas_only to
    false

    Args:
      nvd_dict: deserialized NVD data
      filename: the output filename
      bq: the BQ client object
      deltas_only: whether or not to call get_cve_ids and drop entries for
                   extant CVEs

    Returns:
      local_file: absolute path of newline delimited json, or None if no udpates

    Raises:
      IOError: on failed write to json file
    """
    path = self.config['local_path']
    local_file = path + \
                 filename.replace('.json.gz', '') + \
                 '_newline.json'

    # We can discard the metadata contained in the CVE_data* keys.
    # CVE_Items has what we want.
    cve_list = nvd_dict['CVE_Items']
    scrubbed_list = []

    if deltas_only:
      cve_ids = bq.get_cve_ids(self.config['dataset'])

      for cve in cve_list:
        # todo: come up with more efficient version of the following
        # maybe just accept duplicate entries then remove them with a query
        # once the loading is done? need to think about it.
        if cve['cve']['CVE_data_meta']['ID'] not in cve_ids:
          scrubbed_list.append(cve)
    else:
      # If we're not doing a deltas_only transform, we just take the whole
      # cve_list
      scrubbed_list = cve_list

    # There may be no updates since the last time we ran
    if len(scrubbed_list) == 0:
      return None

    try:
      # The file may already exist, but we want to start with an empty one
      if os.path.isfile(local_file):
        try:
          os.remove(local_file)
        except Exception as e:
          # todo: properly handle exception types here
          raise e

      # This seems clunky, but we want one json object per line for our BQ load
      for cve in scrubbed_list:
        with open(local_file, 'a') as f:
          f.write(json.dumps(cve, indent=None, separators=(',', ':')) + '\n')

    except IOError as e:
      raise IOError('newline delimited json serialization failed in '
                    'ETL.transform: ' + str(e))

    return local_file

  def load(self, bq, filename, bucket_name):
    """Load the NVD data into BQ by way of a GCS bulk load

    Args:
      bq: the BigQuery client object
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

    # I've noticed that from time to time the GCS upload will fail, so to be
    # safe we'll retry 3 times
    keep_trying = True
    try_count = 0
    while keep_trying:
      try:
        # We don't have to check for existance because upload_from_filename
        # should clobber existing files
        blob = bucket.blob(os.path.basename(filename))
        blob.upload_from_filename(filename)
        keep_trying = False
      except Exception as e:
        # i know, i know
        # todo: properly catch exceptions here
        try_count += 1
        if try_count < 3:
          pass
        else:
          raise e

    self.bq_load_from_gcs(bq, self.config['dataset'], filename, bucket_name)

  @staticmethod
  def bq_load_from_gcs(bq, dataset, filename, bucket_name):
    """Caller for BQ.load_from_gcs

    Args:
      bq: the BigQuery client object
      dataset: BQ dataset name
      filename: the local file name, ok if it's relative or absolute, we'll
                strip off directory structure with os.path.basename
      bucket_name: the GCS bucket into which we've already copied the file

    Returns:
      None

    Raises:
      None
    """
    uri = 'gs://' + bucket_name + '/' + os.path.basename(filename)
    bq.load_from_gcs(dataset, uri)