import urllib.request
from urllib.error import ContentTooShortError


class Download(object):
  """Downloader for NVD json feeds.

  Example URLs for NVD json feeds:
  2019: https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-2019.json.gz
  Recent: https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-recent.json.gz

  This is brittle. If NVD changes their file naming scheme or URL this will
  break.

  Attributes:
    config: configuration values
    url_base: URL path for NVD json feeds
    file_prefix: beginning of NVD json feed filename
    file_suffix: ending of NVD json feed filename
  """

  def __init__(self, config):
    """Initialize with config values."""
    self.config = config
    self.url_base = self.config['url_base']

    # The desired file name will go inbetween prefix and suffix, see download
    # function docstring
    self.file_prefix = self.config['file_prefix']
    self.file_suffix = self.config['file_suffix']

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
