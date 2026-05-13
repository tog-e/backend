# ⚡ Tog-e — Хамтдаа өсөх апп

Монгол хосуудын хамтын даалгаврын апп. Хоёр буюу түүнээс дээш хүн нэг акаунт үүсгэж, хамт даалгавар биелүүлэн Тог оноо цуглуулна.

---

## 🚀 Суулгаж эхлэх

```bash
cd tog_e

# Орчин үүсгэх
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Хамаарлууд суулгах
pip install -r requirements.txt

# Сервер эхлүүлэх
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API баримт бичиг: http://localhost:8000/docs

---

## 📱 Аппын бүтэц

```
tog_e/
├── main.py                  # FastAPI апп
├── requirements.txt
├── app/
│   ├── database.py          # SQLite + seed data
│   └── routers/
│       ├── auth.py          # Нэвтрэлт, бүртгүүлэх
│       ├── accounts.py      # Хамтын акаунт
│       ├── tasks.py         # Өдрийн даалгаврууд
│       ├── leaderboard.py   # Тэргүүн жагсаалт
│       └── maps.py          # Газрын зургийн pin-ууд
```

---

## 🔌 API Endpoints

### Нэвтрэлт `/api/auth`

| Method | Path | Тайлбар |
|--------|------|---------|
| POST | `/send-verification` | Имэйл баталгаажуулах код илгээх |
| POST | `/verify-email` | Кодыг шалгах |
| POST | `/signup` | Хамтын акаунт үүсгэх |
| POST | `/login` | Нэвтрэх → JWT token |
| PUT | `/profile/{user_id}` | Профайл тохируулах |

### Даалгаврууд `/api/tasks`

| Method | Path | Тайлбар |
|--------|------|---------|
| GET | `/daily/{account_id}` | Өнөөдрийн даалгаврууд |
| GET | `/all` | Бүх template (ангиллаар шүүх боломжтой) |
| POST | `/{task_id}/approve` | Хэрэглэгч зөвшөөрөх |
| POST | `/{task_id}/complete` | Дуусгасанд тэмдэглэх |

### Тэргүүн жагсаалт `/api/leaderboard`

| Method | Path | Тайлбар |
|--------|------|---------|
| GET | `/` | Бүх акаунт жагсаалт |
| GET | `/my/{account_id}` | Өөрийн байр суурь |

### Газрын зур `/api/maps`

| Method | Path | Тайлбар |
|--------|------|---------|
| GET | `/tasks/{account_id}` | Байршилтай даалгаврууд |

---

## ⚙️ Орчны тохиргоо `.env`

```env
SECRET_KEY=tog-e-super-secret-key-change-me
DB_PATH=tog_e.db
```

---

## 🎯 Даалгаврын ангиллууд

| Ангилал | Тайлбар |
|---------|---------|
| `date_ideas` | Хоёулаа хийх романтик үйл ажиллагаа |
| `positive_habits` | Эерэг дадал хэвшүүлэх |
| `growing` | Хамтдаа хөгжих |
| `challenges` | Гэрэлтэй сорилт |

---

## 🛠️ Дараагийн алхмууд (production)

- [ ] SendGrid / AWS SES имэйл илгээх
- [ ] Google Maps API газрын зурагт холбох
- [ ] Firebase / Expo push notification
- [ ] Redis-ээр token blacklist хийх
- [ ] Docker + Nginx deploy
- [ ] React Native / Flutter frontend
