# 『Machine Learning Platform Engineering』 4장 실습 (홈랩 버전)

[practical-mlops/chapter-4](https://github.com/practical-mlops/chapter-4)를 fork해서, 홈랩 클러스터에서 실습할 수 있게 바꾼 저장소입니다.
클러스터 구성은 [yeonjukim164/kubeflow-argo](https://github.com/yeonjukim164/kubeflow-argo)에 있습니다.
코드는 책 내용을 그대로 따르고, 접속 주소와 버전만 바꿨습니다.

## 원본과 달라진 점

| 항목 | 원본 (책) | 이 저장소 |
|---|---|---|
| 오브젝트 저장소 | MinIO (`port-forward` → localhost:9000) | **SeaweedFS** (S3 호환 API), NodePort **30900** |
| 온라인 스토어 | Redis (`port-forward` → localhost:6379) | **Valkey 9.2** (Redis 호환), NodePort **30379** |
| MLflow | 로컬 `mlflow ui` 또는 부록 A (localhost:5000) | **MLflow 3.17.2**, NodePort **30500** |
| 버킷 생성 | MinIO 웹 콘솔 | `scripts/setup_buckets.py` |
| 접속 정보 | 코드에 직접 작성 | `homelab.env` 환경변수 |
| Python / 패키지 | 3.10 · mlflow 3.0.0 · feast 0.40.1 · xgboost 1.7.6 | 3.12 · mlflow 3.17.2 · feast 0.67.0 · xgboost 3.4.1 (`requirements.txt`) |

SeaweedFS는 S3 호환 API를 제공합니다. 그래서 `s3://` 경로와 `AWS_*` 환경변수 이름을 그대로 쓰지만, AWS와는 관계없고 실제 저장 위치는 홈랩의 SeaweedFS입니다.

코드에서 바꾼 부분 (최소한으로):
- 노트북: MLflow·SeaweedFS 주소를 환경변수에서 읽습니다.
- 노트북: `mlflow.sklearn.log_model(..., serialization_format=CLOUDPICKLE)`
  - MLflow 3.17은 sklearn 모델을 기본으로 skops 형식으로 저장하는데, skops는 신뢰한 타입만 불러옵니다(`sklearn.tree._tree.Tree` 거부).
  - 책과 5장이 모델을 불러오는 방식과 맞추기 위해 pickle 형식으로 저장합니다.
- `feast/feature_store.yaml`: Valkey 주소와 비밀번호를 `${VALKEY_ADDR}`, `${VALKEY_PASSWORD}`로 읽습니다.
- `feast/features.py`: SeaweedFS 주소를 `FEAST_S3_ENDPOINT_URL`에서 읽습니다.

## 준비

```bash
# 1. Python 3.12 가상환경 (uv)
uv venv .venv --python 3.12
uv pip install --python .venv -r requirements.txt
source .venv/bin/activate

# 2. 홈랩 접속 정보 (kubeconfig: ~/.kube/homelab.conf, Valkey 비밀번호를 클러스터 Secret 에서 읽음)
source homelab.env            # 다른 노드로 붙으려면 HOMELAB_NODE=192.168.0.33 source homelab.env

# 3. SeaweedFS 버킷 생성 + Feast 피처 파일 업로드 (책에서 MinIO 콘솔로 하던 작업)
python scripts/setup_buckets.py
```

## 4.1 MLflow

```bash
# Jupyter 를 띄울 때도 homelab.env 를 source 한 셸에서 실행 (8888 은 feast ui 가 쓰므로 8890)
jupyter lab --notebook-dir mlflow --port 8890
```

- `mlflow/data_exploration_and_model_training.ipynb`의 셀을 순서대로 실행합니다.
- MLflow UI는 http://192.168.0.32:30500 입니다(노드 IP는 31~34 중 아무거나 가능).

## 4.2 Feast

```bash
cd feast
feast apply                                        # 레지스트리: s3://feature-registry (SeaweedFS)
python ../feast_retrieval/retrieve_features.py     # 과거 피처 (오프라인 스토어: SeaweedFS 의 Parquet)
feast materialize 2022-09-16T00:00:00 2023-09-17T00:00:00   # 온라인 스토어(Valkey)로 적재
python ../feast_retrieval/retrieve_online_features.py

feast serve      # 4.2.3, http://localhost:6566
curl -X POST http://localhost:6566/get-online-features \
  -H 'Content-Type: application/json' \
  -d '{"features":["demographic:Sex"],"entities":{"user_id":["9f2ac416-06e1-44a0-87bd-d4787c85bf66"]}}'

feast ui         # 4.2.4, http://localhost:8888
```

책의 `curl` 예제에는 `Content-Type: application/json` 헤더가 없습니다. 현재 Feast는 이 헤더가 없으면 422 오류를 냅니다.

5장에서 `feature_store.yaml`을 SeaweedFS에 올리는 스크립트는 주소만 NodePort로 바꿔서 실행하면 됩니다.
```bash
python scripts/push_feature_store_config_to_minio.py --bucket-name=feature-registry \
  --minio-endpoint=192.168.0.32:30900 --access-key=minio --secret-key=minio123 --insecure \
  --feature-store-path feast/feature_store.yaml
```

## 검증 결과 (2026-11-01)

| 단계 | 결과 |
|---|---|
| 노트북 (4.1) | 끝까지 실행됨. test AUC: 결정트리 0.819 · 랜덤포레스트 0.854 · XGBoost 0.727 → 랜덤포레스트 등록, `load_model` 정상 |
| `feast apply` / 과거 피처 | 피처 뷰 3개 생성, `Sex = Male` |
| `feast materialize` | Valkey 키 30,162개 (데이터 행 수와 같음) |
| 온라인 피처 / `feast serve` | `Sex = Male`, `PRESENT` |
| `feast ui` | http://localhost:8888 응답 200 |

데이터를 무작위로 나누기 때문에 AUC 값은 실행할 때마다 조금씩 다릅니다.

## 주의

- SeaweedFS 키(`minio`/`minio123`)는 kubeflow/manifests 기본값입니다. 홈랩 내부망 전용으로만 쓰세요.
- `homelab.env`의 `MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD=false`는 지우지 마세요. MLflow 서버가 다운로드용으로 주는 presigned URL이 클러스터 내부 주소라, PC에서는 아티팩트 다운로드가 멈춥니다.
