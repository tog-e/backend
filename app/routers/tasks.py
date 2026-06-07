"""
Даалгаврын систем
- Өдөр тутам автоматаар даалгавар гаргах
- Хоёулаа зөвшөөрснөөр эхлэх
- Биелүүлэхэд Тог оноо нэмэх
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_db

router = APIRouter()


# ── Схемүүд ──────────────────────────────────────────────

class ApproveTaskRequest(BaseModel):
    user_id: int


class CompleteTaskRequest(BaseModel):
    user_id: int


# ── Туслах функцүүд ──────────────────────────────────────

DAILY_TASK_COUNT = 3  # өдөрт гарах даалгаврын тоо
CATEGORIES = ["date_ideas", "positive_habits", "growing", "challenges"]


async def _ensure_daily_tasks(account_id: int, today: date, db):
    """Өдрийн даалгаврууд байхгүй бол шинэ сонгон үүсгэх."""
    cur = await db.execute(
        "SELECT COUNT(*) FROM daily_tasks WHERE account_id=? AND date=?",
        (account_id, today.isoformat())
    )
    count = (await cur.fetchone())[0]
    if count >= DAILY_TASK_COUNT:
        return

    # Аль хэдийн өгсөн template-үүдийг давхардуулахгүйн тулд авах
    cur = await db.execute(
    "SELECT template_id FROM daily_tasks WHERE account_id=? AND date=?",
    (account_id, today.isoformat())
    )
    used = {r[0] for r in await cur.fetchall()}

    # Ангиллаас тэнцүү хуваарилан сонгох
    selected = []
    for cat in CATEGORIES:
        cur = await db.execute(
            """SELECT id FROM task_templates
               WHERE category=? AND is_active=1
               AND id NOT IN ({})
               ORDER BY RANDOM() LIMIT 1""".format(
                ",".join(map(str, used)) if used else "0"
            ),
            (cat,)
        )
        row = await cur.fetchone()
        if row:
            selected.append(row[0])
            used.add(row[0])
        if len(selected) >= DAILY_TASK_COUNT:
            break

    for tid in selected:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO daily_tasks (account_id, template_id, date) VALUES (?,?,?)",
                (account_id, tid, today.isoformat())
            )
        except Exception:
            pass
    await db.commit()


# ── Endpoint-ууд ─────────────────────────────────────────

@router.get("/daily/{account_id}")
async def get_daily_tasks(account_id: int, db=Depends(get_db)):
    """Өнөөдрийн даалгавруудыг авах."""
    today = date.today()
    await _ensure_daily_tasks(account_id, today, db)

    cur = await db.execute(
        """SELECT
            dt.id, dt.status, dt.tog_earned, dt.completed_at,
            t.title, t.description, t.points, t.category,
            t.location_name, t.latitude, t.longitude,
            (SELECT COUNT(*) FROM task_approvals WHERE daily_task_id=dt.id) as approval_count,
            (SELECT COUNT(*) FROM account_members WHERE account_id=?) as member_count
           FROM daily_tasks dt
           JOIN task_templates t ON t.id=dt.template_id
           WHERE dt.account_id=? AND dt.date=?
           ORDER BY t.points DESC""",
        (account_id, account_id, today.isoformat())
    )
    rows = await cur.fetchall()

    tasks = []
    for r in rows:
        tasks.append({
            "id": r["id"],
            "title": r["title"],
            "description": r["description"],
            "category": r["category"],
            "points": r["points"],
            "status": r["status"],
            "tog_earned": r["tog_earned"],
            "completed_at": r["completed_at"],
            "location_name": r["location_name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "approvals": r["approval_count"],
            "members_needed": r["member_count"],
            "can_start": r["approval_count"] >= r["member_count"],
        })
    return {"date": today.isoformat(), "tasks": tasks}


@router.get("/all")
async def get_all_templates(category: Optional[str] = None, db=Depends(get_db)):
    """Бүх боломжит даалгавруудыг авах."""
    if category:
        cur = await db.execute(
            "SELECT * FROM task_templates WHERE category=? AND is_active=1 ORDER BY points",
            (category,)
        )
    else:
        cur = await db.execute(
            "SELECT * FROM task_templates WHERE is_active=1 ORDER BY category, points"
        )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/{task_id}/approve")
async def approve_task(task_id: int, req: ApproveTaskRequest, db=Depends(get_db)):
    """
    Хэрэглэгч task эхлүүлэхийг зөвшөөрөх.
    Бүх гишүүд зөвшөөрсөн үед task 'in_progress' болно.
    """
    cur = await db.execute(
        "SELECT dt.account_id, dt.status FROM daily_tasks dt WHERE dt.id=?",
        (task_id,)
    )
    task = await cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Даалгавар олдсонгүй")
    if task["status"] == "completed":
        raise HTTPException(status_code=400, detail="Даалгавар аль хэдийн дууссан")

    account_id = task["account_id"]

    # Энэ хэрэглэгч уг account-ийн гишүүн эсэхийг шалгах
    cur = await db.execute(
        "SELECT 1 FROM account_members WHERE account_id=? AND user_id=?",
        (account_id, req.user_id)
    )
    if not await cur.fetchone():
        raise HTTPException(status_code=403, detail="Та энэ account-ийн гишүүн биш байна")

    # Зөвшөөрөл оруулах
    await db.execute(
        "INSERT OR IGNORE INTO task_approvals (daily_task_id, user_id) VALUES (?,?)",
        (task_id, req.user_id)
    )

    # Нийт гишүүдийн тоог шалгах
    cur = await db.execute(
        "SELECT COUNT(*) FROM account_members WHERE account_id=?", (account_id,)
    )
    total_members = (await cur.fetchone())[0]

    cur = await db.execute(
        "SELECT COUNT(*) FROM task_approvals WHERE daily_task_id=?", (task_id,)
    )
    approved = (await cur.fetchone())[0]

    if approved >= total_members:
        await db.execute(
            "UPDATE daily_tasks SET status='in_progress', started_by=? WHERE id=?",
            (req.user_id, task_id)
        )

    await db.commit()
    return {
        "approvals": approved,
        "total_members": total_members,
        "status": "in_progress" if approved >= total_members else "pending",
    }


@router.post("/{task_id}/complete")
async def complete_task(task_id: int, req: CompleteTaskRequest, db=Depends(get_db)):
    """
    Даалгавар биелүүлсэнд тэмдэглэх.
    Тог оноо нэмэгдэнэ.
    """
    cur = await db.execute(
        """SELECT dt.account_id, dt.status, t.points
           FROM daily_tasks dt
           JOIN task_templates t ON t.id=dt.template_id
           WHERE dt.id=?""",
        (task_id,)
    )
    task = await cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Даалгавар олдсонгүй")
    if task["status"] == "completed":
        raise HTTPException(status_code=400, detail="Аль хэдийн дууссан")
    if task["status"] == "pending":
        raise HTTPException(status_code=400, detail="Эхлээд бүгд зөвшөөрөх ёстой")

    now = datetime.utcnow().isoformat()
    await db.execute(
        """UPDATE daily_tasks
           SET status='completed', completed_at=?, tog_earned=?
           WHERE id=?""",
        (now, task["points"], task_id)
    )

    # Account-ийн нийт Тог нэмэх
    await db.execute(
        "UPDATE accounts SET tog_total=tog_total+? WHERE id=?",
        (task["points"], task["account_id"])
    )
    await db.commit()

    return {
        "message": f"🎉 Даалгавар дууслаа! +{task['points']} Тог нэмэгдлээ",
        "tog_earned": task["points"],
    }
class AddRecommendedTaskRequest(BaseModel):
    account_id: int
    title: str
    description: str
    points: int
    category: str
    location_name: str = ""
    latitude: float = None
    longitude: float = None

@router.post("/add-recommended")
async def add_recommended_task(req: AddRecommendedTaskRequest, db=Depends(get_db)):
    """
    AI-с санал болгосон taskийг өнөөдрийн даалгавар болгох.
    Өдөрт 1 удаа л нэмж болно.
    """
    from datetime import date
    today = date.today()

    # Өдөрт 1 удаа шалгах
    cur = await db.execute(
        """SELECT COUNT(*) FROM daily_tasks dt
           JOIN task_templates tt ON tt.id = dt.template_id
           WHERE dt.account_id=? AND dt.date=? AND tt.category='ai_recommended'""",
        (req.account_id, today.isoformat())
    )
    count = (await cur.fetchone())[0]
    if count > 0:
        raise HTTPException(
            status_code=400,
            detail="Өнөөдөр AI-с нэг л даалгавар нэмж болно"
        )

    # Шинэ template үүсгэх
    cur = await db.execute(
        """INSERT INTO task_templates 
           (category, title, description, points, location_name, latitude, longitude)
           VALUES (?,?,?,?,?,?,?)""",
        ('ai_recommended', req.title, req.description, req.points,
         req.location_name, req.latitude, req.longitude)
    )
    template_id = cur.lastrowid

    # Өнөөдрийн daily task болгох
    await db.execute(
        """INSERT INTO daily_tasks (account_id, template_id, date)
           VALUES (?,?,?)""",
        (req.account_id, template_id, today.isoformat())
    )
    await db.commit()

    return {"message": "✅ AI даалгавар нэмэгдлээ!", "template_id": template_id}