"""
Нэвтрэлт — бүртгүүлэх, нэвтрэх, JWT token
"""
from dotenv import load_dotenv
load_dotenv()
import os
import random
import string
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.database import get_db

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "tog-e-secret-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@tog-e.app")


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    partner_emails: list[EmailStr]
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileSetupRequest(BaseModel):
    bio: str
    avatar_url: str = ""


def _make_token(user_id: int, account_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "account_id": account_id,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _gen_code(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))

async def _send_verification_email(email: str, code: str):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    
    if not gmail_user:
        print(f"[Tog-e] {email} → баталгаажуулах код: {code}")
        return
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Tog-e — Баталгаажуулах код"
    msg["From"] = gmail_user
    msg["To"] = email
    
    html = f"""
    <div style="font-family: sans-serif; max-width: 400px; margin: 0 auto;">
        <h1 style="color: #6C3DE8;">Tog-e ⚡</h1>
        <p>Таны баталгаажуулах код:</p>
        <h2 style="background: #F0EBFF; padding: 16px; border-radius: 12px;
                   text-align: center; letter-spacing: 8px; color: #1A1035;">
            {code}
        </h2>
        <p style="color: #8A85A0;">Код 15 минут хүчинтэй.</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, email, msg.as_string())
    except Exception as e:
        print(f"[Tog-e] Имэйл алдаа: {e}")

@router.post("/send-verification")
async def send_verification(email: EmailStr, db=Depends(get_db)):
    code = _gen_code()
    expires = datetime.utcnow() + timedelta(minutes=15)
    await db.execute(
        "UPDATE email_verifications SET used=1 WHERE email=? AND used=0", (email,)
    )
    await db.execute(
        "INSERT INTO email_verifications (email, code, expires_at) VALUES (?,?,?)",
        (email, code, expires.isoformat())
    )
    await db.commit()
    await _send_verification_email(email, code)
    return {"message": f"{email} рүү баталгаажуулах код илгээлээ"}


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db=Depends(get_db)):
    cur = await db.execute(
        """SELECT id FROM email_verifications
           WHERE email=? AND code=? AND used=0 AND expires_at > ?""",
        (req.email, req.code, datetime.utcnow().isoformat())
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Код буруу эсвэл хугацаа дууссан")
    await db.execute(
        "UPDATE email_verifications SET used=1 WHERE id=?", (row["id"],)
    )
    await db.commit()
    return {"verified": True}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest, db=Depends(get_db)):
    all_emails = [req.email] + list(req.partner_emails)
    existing = await db.execute(
        f"SELECT email FROM users WHERE email IN ({','.join('?'*len(all_emails))})",
        all_emails
    )
    rows = await existing.fetchall()
    if rows:
        taken = [r["email"] for r in rows]
        raise HTTPException(status_code=400, detail=f"Имэйл аль хэдийн бүртгэлтэй: {taken}")

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    cur = await db.execute(
        "INSERT INTO accounts (name) VALUES (?)", (f"{req.name}-ийн аян",)
    )
    account_id = cur.lastrowid
    cur = await db.execute(
        "INSERT INTO users (name, email, password) VALUES (?,?,?)",
        (req.name, req.email, hashed)
    )
    user_id = cur.lastrowid
    await db.execute(
        "INSERT INTO account_members (account_id, user_id) VALUES (?,?)",
        (account_id, user_id)
    )
    for partner_email in req.partner_emails:
        temp_pass = bcrypt.hashpw(b"change-me", bcrypt.gensalt()).decode()
        cur = await db.execute(
            "INSERT INTO users (name, email, password) VALUES (?,?,?)",
            (partner_email.split("@")[0], partner_email, temp_pass)
        )
        partner_id = cur.lastrowid
        await db.execute(
            "INSERT INTO account_members (account_id, user_id) VALUES (?,?)",
            (account_id, partner_id)
        )
        await _send_verification_email(partner_email, "Та Tog-e-д урилга авлаа!")

    await db.commit()
    token = _make_token(user_id, account_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "account_id": account_id,
        "message": "Бүртгэл амжилттай! Хамтрагчдад урилга илгээлээ.",
    }


@router.post("/login")
async def login(req: LoginRequest, db=Depends(get_db)):
    cur = await db.execute(
        "SELECT id, password FROM users WHERE email=?", (req.email,)
    )
    user = await cur.fetchone()
    if not user or not bcrypt.checkpw(req.password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Имэйл эсвэл нууц үг буруу")
    cur = await db.execute(
        "SELECT account_id FROM account_members WHERE user_id=?", (user["id"],)
    )
    membership = await cur.fetchone()
    if not membership:
        raise HTTPException(status_code=404, detail="Account олдсонгүй")
    token = _make_token(user["id"], membership["account_id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["id"],
        "account_id": membership["account_id"],
    }

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

@router.post("/forgot-password")
async def forgot_password(email: EmailStr, db=Depends(get_db)):
    code = _gen_code()
    expires = datetime.utcnow() + timedelta(minutes=15)
    await db.execute(
        "UPDATE email_verifications SET used=1 WHERE email=? AND used=0", (email,)
    )
    await db.execute(
        "INSERT INTO email_verifications (email, code, expires_at) VALUES (?,?,?)",
        (email, code, expires.isoformat())
    )
    await db.commit()
    await _send_verification_email(email, code)
    return {"message": f"{email} рүү нууц үг сэргээх код илгээлээ"}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db=Depends(get_db)):
    cur = await db.execute(
        """SELECT id FROM email_verifications
           WHERE email=? AND code=? AND used=0 AND expires_at > ?""",
        (req.email, req.code, datetime.utcnow().isoformat())
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Код буруу эсвэл хугацаа дууссан")
    await db.execute(
        "UPDATE email_verifications SET used=1 WHERE id=?", (row["id"],)
    )
    hashed = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    await db.execute(
        "UPDATE users SET password=? WHERE email=?", (hashed, req.email)
    )
    await db.commit()
    return {"message": "Нууц үг амжилттай өөрчлөгдлөө"}

@router.put("/profile/{user_id}")
async def setup_profile(user_id: int, req: ProfileSetupRequest, db=Depends(get_db)):
    await db.execute(
        "UPDATE users SET bio=?, avatar_url=? WHERE id=?",
        (req.bio, req.avatar_url, user_id)
    )
    await db.commit()
    return {"message": "Профайл шинэчлэгдлээ"}