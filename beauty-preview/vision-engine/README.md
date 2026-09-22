# Giso Beauty Vision Engine

Lightweight post-processing service for beauty-preview.

It does not run an image-generation model. The external AI provider still
performs the image edit. This service detects the target region, builds a
feathered mask, keeps original pixels outside the mask, composites the AI
result only inside the target region, and measures preservation.

Current active service: eyebrows.

Run:
python -m uvicorn app:app --host 127.0.0.1 --port 8010

Keep it on localhost in production.
