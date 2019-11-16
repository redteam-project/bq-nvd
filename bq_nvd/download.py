import urllib.request
from urllib.error import ContentTooShortError


class Download(object):

  def __init__(self):
    self.url_base = 'https://nvd.nist.gov/feeds/json/cve/1.1/'

    # The desired file name will go inbetween prefix and suffix, see download
    # function docstring
    self.file_prefix = 'nvdcve-1.1-'
    self.file_suffix = '.json.gz'

  def download(self, name, local_path):
    """Downloads the NVD JSON feed file

    Args:
      name: which file to retrieve, i.e., modified, recent, 2019, etc.
      local_path: absolute path for the file to be downloaded to, including ending '/'

    Returns:
      local_filename: absolute path to the downloaded file

    Raises:
      ContentTooShortError: if the download fails or is incomplete
    """
    filename = self.file_prefix + name + self.file_suffix
    url = self.url_base + filename
    local_filename = local_path + filename

    try:
      urllib.request.urlretrieve(url, local_filename)
    except ContentTooShortError as e:
      raise e

    return local_filename
