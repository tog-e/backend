"""
Тэргүүн жагсаалт — Тог оноогоор
"""

from fastapi import APIRouter, Depends
from app.database import get_db

router = APIRouter()


@router.get("/")
async def get_leaderboard(limit: int = 20, db=Depends(get_db)):
    """Бүх account-уудыг Тог оноогоор жагсааx."""
    cur = await db.execute(
    """SELECT
        a.id, a.name as account_name, a.tog_total,
        COUNT(DISTINCT am.user_id) as member_count,
        GROUP_CONCAT(DISTINCT u.name) as member_names,
        COUNT(CASE WHEN dt.status='completed' THEN 1 END) as tasks_completed
       FROM accounts a
       LEFT JOIN account_members am ON am.account_id=a.id
       LEFT JOIN users u ON u.id=am.user_id
       LEFT JOIN daily_tasks dt ON dt.account_id=a.id
       GROUP BY a.id
       ORDER BY a.tog_total DESC
       LIMIT ?""",
    (limit,)
    )
    rows = await cur.fetchall()

    board = []
    for i, r in enumerate(rows, 1):
        board.append({
            "rank": i,
            "account_id": r["id"],
            "account_name": r["account_name"],
            "members": r["member_names"],
            "member_count": r["member_count"],
            "tog_total": r["tog_total"],
            "tasks_completed": r["tasks_completed"],
        })
    return {"leaderboard": board}


@router.get("/my/{account_id}")
async def get_my_rank(account_id: int, db=Depends(get_db)):
    """Өөрийн account-ийн байр суурийг авах."""
    cur = await db.execute(
        "SELECT tog_total FROM accounts WHERE id=?", (account_id,)
    )
    me = await cur.fetchone()
    if not me:
        return {"rank": None, "tog_total": 0}

    cur = await db.execute(
        "SELECT COUNT(*)+1 as rank FROM accounts WHERE tog_total > ?",
        (me["tog_total"],)
    )
    rank_row = await cur.fetchone()
    return {"rank": rank_row["rank"], "tog_total": me["tog_total"]}
