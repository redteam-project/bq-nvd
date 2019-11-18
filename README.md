# BigQuery National Vulnerability Database Mirror (bq-nvd)

This project mirrors the [National Vulnerability Database](https://nvd.nist.gov/) (NVD) in Google Cloud BigQuery.

Why would you want to do this? While the NVD's website has nice query features, there are advantages to having the entirety of NVD in a SQL-compliant data warehouse. This also enables you to join the NVD dataset with other datasets.

You can query the Red Team Project's public dataset (red-team-project:bq_nvd.nvd) as an authenticated cloud user. Or you can run your own bq-nvd mirror in your GCP project. See the [Usage](#Usage) section for more details.

## GCP Setup

This project depends upon several Google Cloud services. If you don't already have an account, you can set one up [for free](https://cloud.google.com/free/). Most of what's being described in this project should fall under that free tier, but before setting up your own [GKE cluster](https://cloud.google.com/kubernetes-engine/), be sure to explore the [GCP Calculator](https://cloud.google.com/products/calculator/) so you'll know if you will incur any costs.

## Usage

### Querying the public data set

Once you've logged into GCP, you can query this project's bq-nvd dataset, which is public.

#### Setup

You can use the following example queries from the [Google Cloud Console](https://console.cloud.google.com/bigquery), [gcloud SDK](https://cloud.google.com/sdk/), [client libraries](https://cloud.google.com/bigquery/docs/reference/libraries), or [BigQuery API](https://cloud.google.com/bigquery/docs/reference/rest/). These examples assume usage of the `bq` component of the gcloud SDK.

[gcloud SDK setup instructions](https://cloud.google.com/sdk/install)

#### Example queries

Counting all entries:

```
bq query --project_id red-team-project "SELECT COUNT(cve.CVE_data_meta.ID) as CVE_Count FROM bq_nvd.nvd"
```

Return all Linux CVEs (remove the `LIMIT 1` if you really want to do this, there are more than 8,000):

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

## Maintaining your own dataset

If you want to mirror NVD to your own data set, you can do so by running this tool locally. If you want to keep your mirror up to date, you can deploy this tool as a Kubernetes CronJob.

In either case, the first thing you need to do is update the [config.yml](config.yml) file to match the details of your project. Modify the `project`, `dataset`, and `bucket_name` environment variables in the [CronJob spec](cronjob.yml) file if you're running in Kubernetes. See more below.

You'll also need an IAM service account with the appropriate privileges, as well as its key.

```
gcloud iam service-accounts create bq-nvd
gcloud projects add-iam-policy-binding my-project \
  --member serviceAccount:bq-nvd@my-project.iam.gserviceaccount.com \
  --role roles/storage.admin
gcloud projects add-iam-policy-binding my-project \
  --member serviceAccount:bq-nvd@my-project.iam.gserviceaccount.com \
  --role roles/bigquery.admin
gcloud iam service-accounts keys create ~/service-account-key.json \
  --iam-account bq-nvd@my-project.iam.gserviceaccount.com
```

### Running locally

Follow these steps to run this tool locally. Note that python3 and pip3 are required.

1. Clone this repo

```
git clone https://github.com/redteam-project/bq-nvd
```

2. Modify the [config.yml](config.yml) file as indicated above.

3. Install Python requirements

```
pip install -r requirements.txt
```

4. Invoke the tool

```
GOOGLE_APPLICATION_CREDENTIALS=~/service-account-key.json python ./by-etl.py
```

### Running from a local Docker container

Another option is to run from a local Docker container. In this case, you specify environment variables at runtime and don't need to make any modifications to the source code.

1. Build the container

```
git clone https://github.com/redteam-project/bq-nvd
cd bq-nvd
docker build -t bq-nvd .
```

2. Run the container, specifying your own `project`, `dataset`, and `bucket_name` environment variable values.

```
mkdir ~/keys
mv ~/service-account-key.json ~/keys
docker run \
  -v ~/keys:/keys \
  -e GOOGLE_APPLICATION_CREDENTIALS=/keys/service-account-key.json \
  -e local_path=/usr/local/bq_nvd/ \
  -e bucket_name=bq_nvd_example \
  -e project=my-project \
  -e dataset=bq_nvd_example \
  -e nvd_schema='./schema.json' \
  -e url_base=https://nvd.nist.gov/feeds/json/cve/1.1/ \
  -e file_prefix=nvdcve-1.1- \
  -e file_suffix=.json.gz \
  bq-nvd
```

### Keeping your mirror up to date

This tools is designed to run as a Kubernetes CronJob. Use the following instructions to create your own GKE cluster and deploy it as a CronJob.

#### Creating a GKE cluster

First, create the cluster.

```
gcloud container \
  --project my-project \
  clusters create my-cluster-1 \
  --zone us-central1-a
```

Set up authentication.

```
gcloud container clusters get-credentials --zone us-central1-a my-cluster-1
```

Upload your service account key as a Kubernetes Secret. Learn more about GKE pod authentication [here](https://cloud.google.com/kubernetes-engine/docs/tutorials/authenticating-to-cloud-platform).

```
kubectl create secret generic bq-nvd-iam --from-file=key.json=/path/to/service-account-key.json
```

Build the container image, and push it to GCR.
```
gcloud auth configure-docker
export PROJECT_ID=my-project
git clone https://github.com/redteam-project/bq-nvd
cd bq-nvd
docker build -t gcr.io/${PROJECT_ID}/bq-nvd:v1 .
docker push gcr.io/${PROJECT_ID}/bq-nvd:v1
```

Now, deploy the CronJob.

```
kubectl apply -f cronjob.yml
```

You can adjust the `schedule` value in [cronjob.yml](cronjob.yml) to whatever periodicity you like.
