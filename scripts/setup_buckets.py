"""SeaweedFS 에 실습 버킷을 만들고 Feast 피처 파일을 올림 (책에서 MinIO 콘솔로 하던 작업).

`source homelab.env` 후 저장소 루트에서 실행 (SeaweedFS NodePort 30900):
    python scripts/setup_buckets.py
"""
import os
from pathlib import Path

from minio import Minio

BUCKETS = ["mlflow-datasets", "feature-data-sets", "feature-registry"]
FEATURE_FILES = Path(__file__).resolve().parent.parent / "feast" / "feature_data"

endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:9000").split("://", 1)[-1]
client = Minio(
    endpoint,
    access_key=os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
    secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
    secure=False,
)

for bucket in BUCKETS:
    if client.bucket_exists(bucket):
        print(f"bucket {bucket}: already exists")
    else:
        client.make_bucket(bucket)
        print(f"bucket {bucket}: created")

for parquet in sorted(FEATURE_FILES.glob("*.parquet")):
    client.fput_object("feature-data-sets", parquet.name, str(parquet))
    print(f"uploaded s3://feature-data-sets/{parquet.name}")
