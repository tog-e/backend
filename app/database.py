"""
Мэдээллийн сан — SQLite + aiosqlite
"""

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "tog_e.db")


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                email       TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,          -- bcrypt hash
                bio         TEXT DEFAULT '',
                avatar_url  TEXT DEFAULT '',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL DEFAULT 'Манай аян',
                tog_total   INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Нэг account-д хэдэн хүн ч байж болно (2+)
            CREATE TABLE IF NOT EXISTS account_members (
                account_id  INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                joined_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, user_id)
            );

            -- Имэйл баталгаажуулалт
            CREATE TABLE IF NOT EXISTS email_verifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                code        TEXT NOT NULL,
                expires_at  DATETIME NOT NULL,
                used        INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- Бүх боломжит даалгаврын сан
            CREATE TABLE IF NOT EXISTS task_templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category    TEXT NOT NULL,       -- 'date_ideas','positive_habits','growing','challenges'
                title       TEXT NOT NULL,
                description TEXT DEFAULT '',
                points      INTEGER NOT NULL,
                location_name TEXT DEFAULT '',
                latitude    REAL,
                longitude   REAL,
                is_active   INTEGER DEFAULT 1
            );

            -- Өдөр тутам account-д ногдох даалгаврууд
            CREATE TABLE IF NOT EXISTS daily_tasks (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id   INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
                template_id  INTEGER REFERENCES task_templates(id),
                date         DATE NOT NULL,
                status       TEXT DEFAULT 'pending',  -- pending | in_progress | completed
                started_by   INTEGER REFERENCES users(id),
                completed_at DATETIME,
                tog_earned   INTEGER DEFAULT 0,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(account_id, template_id, date)
            );

            -- Task эхлүүлэхэд хоёулаа зөвшөөрөх
            CREATE TABLE IF NOT EXISTS task_approvals (
                daily_task_id INTEGER REFERENCES daily_tasks(id) ON DELETE CASCADE,
                user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                approved_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (daily_task_id, user_id)
            );
        """)
        await db.commit()

        # Анхны даалгаврын мэдээлэл оруулах
        await _seed_tasks(db)
        await db.commit()


async def _seed_tasks(db):
    count = await db.execute("SELECT COUNT(*) FROM task_templates")
    row = await count.fetchone()
    if row[0] > 0:
        return

    tasks = [
        # Date ideas
        ("date_ideas", "Хамтдаа кофе ууцгаая", "Ойр дотны кофе шопод очиж цай кофе хуваалцаарай", 50, "Nomads Coffee", 47.9077, 106.8832),
        ("date_ideas", "Шинэ ресторан туршицгаая", "Нэг хэзээ ч очиж байгаагүй ресторанд хамтдаа очоорой", 70, "", None, None),
        ("date_ideas", "Үүрийн цайг хамтдаа харцгаая", "Зайсан толгой эсвэл ойр дотны цэцэрлэгт хүрээлэнд гарцгаая", 80, "Zaisan", 47.8742, 106.9174),
        ("date_ideas", "Кино үзцгэеэ", "Шинэ кино сонгоод хамтдаа үзэцгэе", 40, "Tengis Cinema", 47.9149, 106.9228),
        ("date_ideas", "Цэцэрлэгт алхцгаая", "Байгальд зугаалж хамтдаа алхаарай", 35, "Sükhbaatar Square", 47.9188, 106.9177),

        # Positive habits
        ("positive_habits", "Хамтдаа дасгал хийцгэеэ", "30 минут хамтдаа спорт хийгээрэй", 60, "", None, None),
        ("positive_habits", "Хамтдаа ном унших", "20 минут аль нэг ном уншаад хуваалцаарай", 30, "", None, None),
        ("positive_habits", "Эрт босоорой", "Хоёулаа 7 цаасаас өмнө босоорой", 25, "", None, None),
        ("positive_habits", "Эрүүл хоол бэлдцгэеэ", "Гэртээ хамтдаа эрүүл хоол хийгээрэй", 45, "", None, None),
        ("positive_habits", "Дижитал детокс", "2 цаг гар утасгүй хамтдаа өнгөрөөгөөрэй", 55, "", None, None),

        # Growing with right person
        ("growing", "Мөрөөдлийнхөө тухай ярилцаарай", "Ирээдүйн мөрөөдлөө хуваалцаад дэмжигч болоорой", 40, "", None, None),
        ("growing", "Шинэ ур чадвар хамтдаа суралцаарай", "YouTube эсвэл курсаас нэг зүйл хамтдаа сураарай", 65, "", None, None),
        ("growing", "Талархлын дэвтэр", "Өдрийн 3 сайн зүйлийг хуваалцаарай", 20, "", None, None),
        ("growing", "Хоорондоо feedback өгцгөөе", "Нэг давуу тал, нэг хөгжих зүйл хэлэлцэцгэе", 50, "", None, None),

        # Challenges
        ("challenges", "7 хоногийн challenge", "7 хоног дараалан нэг эерэг дадал хэвшүүлэх", 150, "", None, None),
        ("challenges", "Монголын аймаг зорчицгоо", "Нэг шинэ аймаг эсвэл газар зорьцгоо", 200, "", None, None),
        ("challenges", "Сарын хуваарь гаргацгаая", "Дараагийн сарын хамтын төлөвлөгөөгөө тогтооцгоо", 80, "", None, None),
        ("challenges", "Гэрэл зурагны challenge", "7 хоног дотор хамтдаа 7 гэрэл зураг авцгаа", 90, "", None, None),
    ]

    await db.executemany("""
        INSERT INTO task_templates (category, title, description, points, location_name, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, tasks)
