"""
Хамтын акаунт — мэдээлэл авах, гишүүдийг харах
"""

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_db

router = APIRouter()


@router.get("/{account_id}")
async def get_account(account_id: int, db=Depends(get_db)):
    cur = await db.execute(
        "SELECT id, name, tog_total, created_at FROM accounts WHERE id=?",
        (account_id,)
    )
    acc = await cur.fetchone()
    if not acc:
        raise HTTPException(status_code=404, detail="Account олдсонгүй")

    cur = await db.execute(
        """SELECT u.id, u.name, u.email, u.bio, u.avatar_url, u.created_at
           FROM users u
           JOIN account_members am ON am.user_id=u.id
           WHERE am.account_id=?""",
        (account_id,)
    )
    members = [dict(r) for r in await cur.fetchall()]

    return {
        "id": acc["id"],
        "name": acc["name"],
        "tog_total": acc["tog_total"],
        "created_at": acc["created_at"],
        "members": members,
    }
