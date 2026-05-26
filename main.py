"""
Tog-e — Хамтдаа өсөх апп
FastAPI backend
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, accounts, tasks, leaderboard, maps, ai, completions
app = FastAPI(
    title="Tog-e API",
    description="Хосуудын хамтын даалгаврын апп",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()

#1
app.include_router(auth.router, prefix="/api/auth", tags=["Нэвтрэлт"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Хамтын акаунт"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Даалгаврууд"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["Тэргүүн жагсаалт"])
app.include_router(maps.router, prefix="/api/maps", tags=["Газрын зур"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])
app.include_router(completions.router, prefix="/api/completions", tags=["Биелүүлэлт"])

@app.get("/")
async def root():
    return {"message": "Tog-e API ажиллаж байна ⚡", "version": "1.0.0"}
