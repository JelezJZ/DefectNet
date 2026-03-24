from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from datetime import datetime, timezone
from src.database.models import Inspection
from src.services.websocket import manager
from src.database.models import SessionLocal

router = APIRouter()

@router.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket для реального времени обновлений"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Ждём сообщения от клиента (например, ping)
            data = await websocket.receive_text()
            
            # Можно отправить текущую статистику
            stats = await get_realtime_stats()
            await websocket.send_json(stats)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def get_realtime_stats():
    """Получить статистику в реальном времени"""
    # Последние 10 проверок
    with SessionLocal() as db:
        recent = db.query(Inspection)\
            .order_by(Inspection.timestamp.desc())\
            .limit(10)\
            .all()
    
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'recent_inspections': len(recent),
            'active_users': len(manager.active_connections),
            'last_inspection': recent[0].timestamp.isoformat() if recent else None
        }
    