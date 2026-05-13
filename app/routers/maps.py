"""
Газрын зур — байршилтай даалгаврууд
"""

from datetime import date
from fastapi import APIRouter, Depends
from app.database import get_db

router = APIRouter()


@router.get("/tasks/{account_id}")
async def get_map_tasks(account_id: int, db=Depends(get_db)):
    """
    Газрын зурагт харуулах байршилтай даалгавруудыг авах.
    Өнөөдрийн болон биелээгүй байгаа даалгаврууд гарна.
    """
    today = date.today()
    cur = await db.execute(
        """SELECT
            dt.id, dt.status,
            t.title, t.points, t.category,
            t.location_name, t.latitude, t.longitude
           FROM daily_tasks dt
           JOIN task_templates t ON t.id=dt.template_id
           WHERE dt.account_id=?
             AND dt.date=?
             AND t.latitude IS NOT NULL
             AND dt.status != 'completed'
           ORDER BY t.points DESC""",
        (account_id, today.isoformat())
    )
    rows = await cur.fetchall()

    pins = []
    for r in rows:
        pins.append({
            "task_id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "points": r["points"],
            "status": r["status"],
            "location_name": r["location_name"],
            "lat": r["latitude"],
            "lng": r["longitude"],
        })
    return {"pins": pins}
