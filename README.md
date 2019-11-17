# BigQuery National Vulnerability Database (bq-nvd)

This project mirrors the [National Vulnerability Database](https://nvd.nist.gov/) (NVD) in Google Cloud BigQuery.

You can query the Red Team Project's public dataset (red-team-project:bq_nvd.nvd) as an authenticated cloud user. Or you can run your own bq-nvd mirror in your GCP project. See the Usage section for more details.

## GCP Setup

This project depends on serveral Google Cloud services. If you don't already have an account, you can set one up [for free](https://cloud.google.com/free/). Most of what's being described in this project should fall under that free tier, but before setting up your own [GKE cluster](https://cloud.google.com/kubernetes-engine/), be sure to explore the [GCP Calculator](https://cloud.google.com/products/calculator/) so you'll know if you will incur any costs.

## Usage

### Querying the public data set

Once you've logged into GCP, you can query this project's bq-nvd dataset, which is public.

#### Setup

You can use the following example queries from the [Google Cloud Console](https://console.cloud.google.com/bigquery), [gcloud SDK](https://cloud.google.com/sdk/), [client libraries](https://cloud.google.com/bigquery/docs/reference/libraries), or [BigQuery API])(https://cloud.google.com/bigquery/docs/reference/rest/). These examples assume usage of the `bq` component of the gcloud SDK.

[gcloud SDK setup instructions](https://cloud.google.com/sdk/install)

#### Example queries

Counting all entries:

```
bq query --project_id red-team-project "SELECT COUNT(cve.CVE_data_meta.ID) as CVE_Count FROM bq_nvd.nvd"
```

Return all Linux CVEs (remove the `LIMIT 1` if you really want to do this, there are over 8,000):

```
cat <<EOF >query.txt
SELECT
  *
FROM
  bq_nvd.nvd
WHERE
  EXISTS (
  SELECT
    1
  FROM
    UNNEST(configurations.nodes) AS nodes
  WHERE
    EXISTS (
    SELECT
      1
    FROM
      UNNEST(nodes.cpe_match) AS cpe_match
    WHERE
      cpe_match.cpe23Uri LIKE '%linux%' ) )
LIMIT 1
EOF
bq query --project_id red-team-project --use_legacy_sql=false --format=prettyjson "`cat query.txt`"
```

## Running locally
