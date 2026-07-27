from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.auth.jwt_handler import get_current_user
from src.database.models import User

router = APIRouter(tags=["Get images"])


@router.get("/results/{file_path:path}")
async def get_result_image(
    file_path: str, current_user: User = Depends(get_current_user)
):
    """Получите изображение с результатами"""

    from src.api.main import RESULTS_DIR

    file_path = RESULTS_DIR / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)


@router.get("/uploads/{file_path:path}")
async def get_original_image(
    file_path: str, current_user: User = Depends(get_current_user)
):
    """Получите оригинальное изображение"""

    from src.api.main import UPLOAD_DIR

    file_path = UPLOAD_DIR / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)
