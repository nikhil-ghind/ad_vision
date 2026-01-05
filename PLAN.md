# Ad Vision

## Project Overview
Distributed video ad platform for high-throughput impression tracking (100k+ daily). Integrates a TensorFlow model for automated video content analysis to enable AI-driven ad targeting. Django backend with React frontend, Kafka for event streaming, AWS S3/CloudFront for video delivery.

## Tech Stack
- **Backend:** Django 4.2+, Django REST Framework, Celery
- **Frontend:** React 18, TypeScript, Tailwind CSS
- **ML:** TensorFlow 2.15+, TensorFlow Hub (video classification models)
- **Streaming:** Apache Kafka 3.x, confluent-kafka-python
- **Storage:** PostgreSQL 15+, AWS S3, Redis
- **CDN:** AWS CloudFront
- **Containerization:** Docker, Docker Compose
- **Monitoring:** Prometheus, Grafana

## Architecture Overview
```
┌────────┐   REST   ┌──────────────┐  Kafka  ┌──────────────┐
│ React  │ ◄──────► │ Django API   │ ──────► │ Impression   │
│ Client │          │ (Ads/Videos) │         │ Tracker      │
└────────┘          └──────┬───────┘         └──────┬───────┘
                           │                        │
                    ┌──────┴───────┐         ┌──────┴───────┐
                    │ Celery       │         │ PostgreSQL   │
                    │ (ML Pipeline)│         │ (Analytics)  │
                    └──────┬───────┘         └──────────────┘
                           │
                    ┌──────┴───────┐
                    │ TensorFlow   │
                    │ Content      │
                    │ Analyzer     │
                    └──────────────┘
```

- **Django API:** CRUD for videos, ads, campaigns; ad-serving endpoint returns targeted ads
- **React Dashboard:** Campaign management, analytics views, video upload
- **TensorFlow Analyzer:** Celery worker processes uploaded videos, extracts content labels/embeddings
- **Kafka Pipeline:** Impression events (view, click, complete) streamed to Kafka, consumed by analytics aggregator
- **Ad Targeting Engine:** Matches ad campaigns to video content using ML-generated labels and audience segments
- **CloudFront CDN:** Serves video assets with signed URLs

## Phase 1: Django Backend & Data Models
**Goal:** Build the core API with data models for videos, ads, campaigns, and impressions.

### Tasks
1. Project structure:
   ```
   backend/
   ├── manage.py
   ├── config/
   │   ├── settings.py        # Django settings, env-based config
   │   ├── urls.py
   │   └── celery.py          # Celery app config
   ├── videos/
   │   ├── models.py          # Video, VideoContentLabel
   │   ├── serializers.py
   │   ├── views.py           # VideoViewSet (CRUD + upload)
   │   └── urls.py
   ├── ads/
   │   ├── models.py          # Ad, Campaign, TargetingRule
   │   ├── serializers.py
   │   ├── views.py           # AdViewSet, CampaignViewSet, serve_ad()
   │   └── urls.py
   ├── impressions/
   │   ├── models.py          # Impression (video_id, ad_id, event_type, timestamp)
   │   ├── views.py           # track_impression() — lightweight POST
   │   └── urls.py
   └── requirements.txt
   ```
2. `videos/models.py`:
   - `class Video` — fields: `id`, `title`, `s3_key`, `cloudfront_url`, `duration_seconds`, `status` (pending/analyzed/failed), `uploaded_at`
   - `class VideoContentLabel` — fields: `video` (FK), `label`, `confidence`, `model_version`
3. `ads/models.py`:
   - `class Campaign` — fields: `name`, `budget_cents`, `spent_cents`, `daily_cap`, `start_date`, `end_date`, `status`
   - `class Ad` — fields: `campaign` (FK), `creative_s3_key`, `click_url`, `ad_type` (pre-roll/mid-roll/banner)
   - `class TargetingRule` — fields: `campaign` (FK), `target_labels` (JSONField list of content labels), `min_confidence`
4. `impressions/models.py`:
   - `class Impression` — fields: `video` (FK), `ad` (FK), `event_type` (view/click/complete/skip), `user_session`, `timestamp`, `metadata` (JSONField)
5. `ads/views.py` — `serve_ad(video_id)`: queries active campaigns whose targeting labels match the video's content labels, picks highest-bid ad, returns ad creative URL.
6. Write migrations, seed data fixtures for testing.

## Phase 2: Video Upload & S3/CloudFront Integration
**Goal:** Enable video upload to S3 with CloudFront delivery URLs.

### Tasks
1. Add `boto3` and `django-storages` to requirements.
2. `videos/services.py`:
   - `generate_presigned_upload_url(filename) -> str` — S3 presigned PUT URL
   - `generate_cloudfront_url(s3_key) -> str` — signed CloudFront URL with expiry
   - `get_video_metadata(s3_key) -> dict` — fetch S3 object metadata (size, content-type)
3. Update `videos/views.py`:
   - `POST /api/videos/upload-url/` — returns presigned URL for client-side upload
   - `POST /api/videos/confirm-upload/` — client confirms upload, triggers ML analysis task
4. Configure S3 bucket with lifecycle rules (move to Glacier after 90 days).
5. Create CloudFront distribution config (origin = S3 bucket, signed URLs enabled).
6. Add `config/aws.py` — centralized AWS config with `AWS_REGION`, `S3_BUCKET`, `CLOUDFRONT_DOMAIN` from env vars.

## Phase 3: TensorFlow Content Analysis Pipeline
**Goal:** Process uploaded videos through a TensorFlow model to extract content labels for ad targeting.

### Tasks
1. Create ML module:
   ```
   ml/
   ├── __init__.py
   ├── analyzer.py            # VideoContentAnalyzer class
   ├── preprocessing.py       # Frame extraction, resizing
   └── tasks.py               # Celery tasks
   ```
2. `ml/preprocessing.py`:
   - `extract_frames(video_path, fps=1) -> list[np.ndarray]` — use OpenCV to sample frames at 1 FPS
   - `preprocess_frame(frame, target_size=(224,224)) -> np.ndarray` — resize, normalize
3. `ml/analyzer.py`:
   - `class VideoContentAnalyzer`:
     - `__init__` — loads TF Hub model (e.g., `movinet_a2_base` for video classification or `efficientnet` for frame-level)
     - `analyze_video(video_path) -> list[dict]` — extracts frames, runs inference, returns `[{"label": str, "confidence": float}]`
     - `get_embedding(video_path) -> np.ndarray` — returns feature vector for similarity matching
4. `ml/tasks.py`:
   - `@celery_app.task def analyze_video_task(video_id)`:
     - Download video from S3 to temp file
     - Run `VideoContentAnalyzer.analyze_video()`
     - Save `VideoContentLabel` records to DB
     - Update `Video.status` to "analyzed"
     - Clean up temp file
5. Wire up: `videos/views.py` `confirm-upload` triggers `analyze_video_task.delay(video_id)`.
6. Add Celery worker config to `config/celery.py` with Redis broker.

## Phase 4: Kafka Impression Tracking Pipeline
**Goal:** Stream impression events through Kafka for scalable, decoupled analytics processing.

### Tasks
1. Add `confluent-kafka` to requirements.
2. Create Kafka module:
   ```
   streaming/
   ├── __init__.py
   ├── producer.py            # KafkaImpressionProducer
   ├── consumer.py            # KafkaImpressionConsumer (analytics aggregator)
   ├── schemas.py             # Avro/JSON schemas for impression events
   └── management/
       └── commands/
           └── run_consumer.py  # Django management command
   ```
3. `streaming/producer.py`:
   - `class KafkaImpressionProducer`:
     - `__init__` — connects to Kafka brokers, configures `impressions` topic
     - `send(event: ImpressionEvent)` — serializes and produces with delivery callback
     - Batch config: `linger.ms=10`, `batch.size=16384`
4. `streaming/consumer.py`:
   - `class KafkaImpressionConsumer`:
     - Subscribes to `impressions` topic
     - `process_batch(messages)` — aggregates impressions per (video_id, ad_id, event_type, hour) and bulk-upserts to `impression_aggregates` table
     - Commit offsets after successful DB write
5. Update `impressions/views.py`:
   - `POST /api/impressions/track/` — lightweight endpoint: validate, produce to Kafka, return 202
   - No direct DB write on the hot path
6. Create `impressions/models.py` — add `ImpressionAggregate` model: `video_id`, `ad_id`, `event_type`, `hour`, `count`.
7. Docker Compose: add Kafka (Kraft mode) and Zookeeper services.
8. Create Kafka topic setup script: `scripts/create_topics.sh`.

## Phase 5: React Frontend Dashboard
**Goal:** Build campaign management and analytics dashboard.

### Tasks
1. Create React app:
   ```
   frontend/
   ├── src/
   │   ├── App.tsx
   │   ├── api/
   │   │   └── client.ts       # Axios instance, API functions
   │   ├── pages/
   │   │   ├── Dashboard.tsx    # Overview: total impressions, spend, top videos
   │   │   ├── Videos.tsx       # Video list, upload, content labels
   │   │   ├── Campaigns.tsx    # Campaign CRUD, targeting rules
   │   │   └── Analytics.tsx    # Charts: impressions over time, CTR, fill rate
   │   ├── components/
   │   │   ├── VideoUploader.tsx    # Presigned URL upload with progress bar
   │   │   ├── CampaignForm.tsx     # Create/edit campaign with targeting
   │   │   ├── ImpressionChart.tsx  # Recharts timeseries
   │   │   └── ContentLabels.tsx    # Display ML-generated labels
   │   └── hooks/
   │       ├── useVideos.ts
   │       └── useCampaigns.ts
   ├── package.json
   └── Dockerfile
   ```
2. `api/client.ts` — Axios instance with base URL, JWT interceptor; functions: `getVideos()`, `uploadVideo()`, `getCampaigns()`, `createCampaign()`, `getAnalytics(filters)`.
3. `VideoUploader.tsx` — requests presigned URL, uploads via XMLHttpRequest with progress callback, calls confirm endpoint.
4. `Analytics.tsx` — date range picker, filters by campaign/video; renders line chart (impressions/day), bar chart (CTR by content label), table of top-performing ads.
5. Dockerfile for React app (nginx-based serve of build output).

## Phase 6: Ad Targeting Engine & Optimization
**Goal:** Implement intelligent ad-to-video matching based on ML content labels.

### Tasks
1. Create `ads/targeting.py`:
   - `select_ad(video_id) -> Ad | None`:
     - Fetch video's content labels from DB
     - Query active campaigns where `TargetingRule.target_labels` overlaps with video labels AND `confidence >= min_confidence`
     - Filter by budget (not exceeded daily cap) and date range
     - Rank by effective CPM (campaign bid / 1000)
     - Return top ad, or None if no match
   - `compute_content_similarity(video_labels, target_labels) -> float` — Jaccard similarity score
2. Create `ads/pacing.py`:
   - `check_budget(campaign_id) -> bool` — verify daily spend < daily_cap
   - `record_spend(campaign_id, cost_cents)` — atomic increment using F() expressions
3. Add API endpoint `GET /api/ads/serve/?video_id=X` that calls `select_ad()` and logs a `view` impression via Kafka.
4. Write unit tests for targeting logic with various campaign/label combinations.

## Phase 7: Docker Compose & Monitoring
**Goal:** Full stack deployment with monitoring.

### Tasks
1. `docker-compose.yml` services: `django`, `celery-worker`, `react`, `postgres`, `redis`, `kafka`, `prometheus`, `grafana`.
2. Prometheus config scraping Django `/metrics` (django-prometheus).
3. Grafana dashboards: impressions/second, ad fill rate, ML pipeline processing time, Kafka consumer lag.
4. `Makefile` with targets: `up`, `down`, `migrate`, `seed`, `test`, `load-test`.
5. Load test script using Locust: simulate 1000 concurrent viewers requesting ads and tracking impressions.
