"""
Task биелүүлэлт — зураг, location, хоёр хүний баталгаа
"""

import os
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.database import get_db

router = APIRouter()


class SubmitCompletionRequest(BaseModel):
    daily_task_id: int
    submitted_by: int
    photo_base64: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ReviewCompletionRequest(BaseModel):
    completion_id: int
    reviewed_by: int
    decision: str  # approved | rejected


@router.post("/submit")
async def submit_completion(req: SubmitCompletionRequest, db=Depends(get_db)):
    """
    Хэрэглэгч task биелүүлсэнээ зураг болон байршлын хамт илгээх.
    """
    # Task байгаа эсэхийг шалгах
    cur = await db.execute(
        "SELECT id, status, account_id FROM daily_tasks WHERE id=?",
        (req.daily_task_id,)
    )
    task = await cur.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail="Даалгавар олдсонгүй")
    if task["status"] == "completed":
        raise HTTPException(status_code=400, detail="Даалгавар аль хэдийн дууссан")

    # Зураг хадгалах
    photo_url = None
    if req.photo_base64:
        photo_dir = "photos"
        os.makedirs(photo_dir, exist_ok=True)
        photo_filename = f"{photo_dir}/completion_{req.daily_task_id}_{req.submitted_by}_{int(datetime.utcnow().timestamp())}.jpg"
        with open(photo_filename, "wb") as f:
            f.write(base64.b64decode(req.photo_base64))
        photo_url = photo_filename

    # Өмнөх pending_review байгаа completion-г устгах
    await db.execute(
        "DELETE FROM task_completions WHERE daily_task_id=? AND submitted_by=? AND status='pending_review'",
        (req.daily_task_id, req.submitted_by)
    )

    # Шинэ completion үүсгэх
    cur = await db.execute(
        """INSERT INTO task_completions 
           (daily_task_id, submitted_by, photo_url, latitude, longitude)
           VALUES (?,?,?,?,?)""",
        (req.daily_task_id, req.submitted_by, photo_url, req.latitude, req.longitude)
    )
    completion_id = cur.lastrowid
    await db.commit()

    return {
        "completion_id": completion_id,
        "message": "Биелүүлэлт илгээгдлээ! Хамтрагч баталгаажуулахыг хүлээж байна.",
        "status": "pending_review"
    }


@router.get("/pending/{account_id}")
async def get_pending_completions(account_id: int, db=Depends(get_db)):
    """
    Баталгаажуулахыг хүлээж байгаа биелүүлэлтүүдийг авах.
    """
    cur = await db.execute(
        """SELECT 
            tc.id, tc.submitted_at, tc.photo_url, tc.latitude, tc.longitude,
            tc.submitted_by, tc.daily_task_id,
            u.name as submitter_name,
            t.title as task_title, t.points as task_points
           FROM task_completions tc
           JOIN daily_tasks dt ON dt.id = tc.daily_task_id
           JOIN task_templates t ON t.id = dt.template_id
           JOIN users u ON u.id = tc.submitted_by
           WHERE dt.account_id=? AND tc.status='pending_review'
           ORDER BY tc.submitted_at DESC""",
        (account_id,)
    )
    rows = await cur.fetchall()
    return {"pending": [dict(r) for r in rows]}


@router.post("/review")
async def review_completion(req: ReviewCompletionRequest, db=Depends(get_db)):
    """
    Хамтрагч биелүүлэлтийг зөвшөөрөх эсвэл татгалзах.
    """
    if req.decision not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="decision 'approved' эсвэл 'rejected' байх ёстой")

    # Completion байгаа эсэхийг шалгах
    cur = await db.execute(
        """SELECT tc.id, tc.daily_task_id, tc.submitted_by, dt.account_id
           FROM task_completions tc
           JOIN daily_tasks dt ON dt.id = tc.daily_task_id
           WHERE tc.id=? AND tc.status='pending_review'""",
        (req.completion_id,)
    )
    completion = await cur.fetchone()
    if not completion:
        raise HTTPException(status_code=404, detail="Биелүүлэлт олдсонгүй")

    # Өөрийнхийгөө баталгаажуулах боломжгүй
    if completion["submitted_by"] == req.reviewed_by:
        raise HTTPException(status_code=400, detail="Өөрийнхөө биелүүлэлтийг баталгаажуулах боломжгүй")

    # Review хадгалах
    await db.execute(
        "INSERT INTO completion_reviews (completion_id, reviewed_by, decision) VALUES (?,?,?)",
        (req.completion_id, req.reviewed_by, req.decision)
    )

    if req.decision == "approved":
        # Task completed болгох
        await db.execute(
            "UPDATE task_completions SET status='approved' WHERE id=?",
            (req.completion_id,)
        )
        # Daily task completed болгох
        cur = await db.execute(
            "SELECT t.points FROM task_completions tc JOIN daily_tasks dt ON dt.id=tc.daily_task_id JOIN task_templates t ON t.id=dt.template_id WHERE tc.id=?",
            (req.completion_id,)
        )
        task_data = await cur.fetchone()
        points = task_data["points"] if task_data else 0

        await db.execute(
            "UPDATE daily_tasks SET status='completed', completed_at=?, tog_earned=? WHERE id=?",
            (datetime.utcnow().isoformat(), points, completion["daily_task_id"])
        )
        # Account-ийн Тог нэмэх
        await db.execute(
            "UPDATE accounts SET tog_total=tog_total+? WHERE id=?",
            (points, completion["account_id"])
        )
        await db.commit()
        return {"message": f"🎉 Баталгаажлаа! +{points} Тог нэмэгдлээ!", "tog_earned": points}
    else:
        # Rejected — task дахин in_progress болгох
        await db.execute(
            "UPDATE task_completions SET status='rejected' WHERE id=?",
            (req.completion_id,)
        )
        await db.commit()
        return {"message": "Биелүүлэлт татгалзагдлаа. Дахин оролдоорой!"}


@router.get("/{completion_id}/photo")
async def get_completion_photo(completion_id: int, db=Depends(get_db)):
    """
    Биелүүлэлтийн зургийг авах.
    """
    cur = await db.execute(
        "SELECT photo_url FROM task_completions WHERE id=?",
        (completion_id,)
    )
    row = await cur.fetchone()
    if not row or not row["photo_url"]:
        raise HTTPException(status_code=404, detail="Зураг олдсонгүй")
    
    with open(row["photo_url"], "rb") as f:
        photo_data = base64.b64encode(f.read()).decode()
    
    return {"photo_base64": photo_data}