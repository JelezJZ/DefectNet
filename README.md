# DefectNet — PCB Defect Detection

An automated Printed Circuit Board (PCB) defect detection system based on YOLO11.

## Features

- 🎯 Detection of 5 defect types: short, open_circuit, mouse_bite, spur, spurious_copper
- 🚀 FastAPI backend with REST API
- 🖥️ Web interface for image uploads
- 📊 Statistics and inspection history
- 💾 PostgreSQL for storing inspection results

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd DefectNet

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env for your environment (especially JWT_SECRET_KEY!)

# Download pretrained models
python scripts/download_models.py

# Optional: Train models via Jupyter (notebooks/)
```

### Configuration

⚠️ **IMPORTANT**: Configure your `.env` file before running the application:

```bash
# Generate a secure JWT secret key
openssl rand -hex 32

# Copy the generated output into .env:
# JWT_SECRET_KEY=your_32_character_key_here
```

📖 Detailed guide: [CONFIG.md](CONFIG.md)  
🚀 Quick env setup status: [ENV_SETUP.md](ENV_SETUP.md)

## Getting Started

### Backend (API)

```bash
python -m src.api.main
```

API available at: http://localhost:8000  
Swagger UI documentation: http://localhost:8000/docs

### Frontend

The frontend is served directly by the FastAPI application:
- Main page: `http://localhost:8000/`
- Dashboard: `http://localhost:8000/dashboard`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /auth/register` | User registration |
| `POST /auth/login` | User login and JWT retrieval |
| `GET /auth/me` | Current user profile |
| `POST /detect` | Single image defect detection |
| `POST /batch-detect` | Synchronous batch detection |
| `POST /batch/upload` | Asynchronous batch processing (Celery) |
| `GET /batch/status/{batch_id}` | Celery batch task status |
| `GET /history/{inspection_id}` | Specific inspection details |
| `GET /health` | API health check |
| `GET /history` | Inspection history list |
| `GET /analytics/dashboard` | Analytics dashboard data |
| `GET /defect-info` | Defect type information |
| `GET /models/available` | Models available for `detect` |
| `GET /models/list` | Detailed model metadata |
| `POST /models/compare` | Compare multiple models on a single image |
| `GET /export/pdf/{inspection_id}` | Export PDF report |
| `GET /export/json/{inspection_id}` | Export single inspection to JSON file |
| `GET /export/image/{inspection_id}?format=png|jpeg` | Export processed output image |
| `GET /export/csv` | Export inspection history to CSV |
| `GET /results/{file_path:path}` | Access output result images |
| `GET /uploads/{file_path:path}` | Access original uploaded images |
| `GET /dashboard` | HTML analytics dashboard |
| `GET /` | HTML detection user interface |

## Project Structure

```
DefectNet/
├── alembic/          # Database migrations
├── src/              # Source code (API, models, DB)
├── frontend/         # Web UI assets
├── models/           # Pretrained model weights
├── datasets/         # Datasets (gitignored)
├── storage/          # Uploaded files and output results
├── runs/             # YOLO training logs and runs
├── notebooks/        # Jupyter notebooks for training
├── scripts/          # Utility scripts (download_models.py)
└── tests/            # Pytest tests
```

## System Requirements

- Python 3.10+
- CUDA (optional, recommended for GPU acceleration)
- 4GB+ RAM

## Important Notes

- In production mode, `ALLOWED_ORIGINS=*` is strictly disallowed (the application will fail to start if `ENVIRONMENT=production`).
- Valid `DATABASE_URL` and `MODEL_PATH` variables in `.env` are required for startup.

## License

MIT