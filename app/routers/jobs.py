"""
Zangia.mn API-с ажлын зар татах
"""
import httpx
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_jobs(limit: int = 20, page: int = 1):
    """Zangia.mn-с ажлын зарууд татах"""
    try:
        jobs = await fetch_zangia_jobs(limit, page)
        return {"jobs": jobs, "total": len(jobs)}
    except Exception as e:
        return {"jobs": [], "error": str(e)}

async def fetch_zangia_jobs(limit: int = 20, page: int = 1):
    url = f"https://new-api.zangia.mn/api/jobs/search?limit={limit}&page={page}&isSortByJobs=true&time=1"
    
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.zangia.mn/",
        }, timeout=15)
        
        data = res.json()
        jobs = []
        items = data.get("items", [])
        
        for item in items:
            jobs.append({
                "id": item.get("id"),
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "location": item.get("address", "Улаанбаатар"),
                "salary": item.get("salary_phrase", ""),
                "url": f"https://www.zangia.mn/job/{item.get('code', '')}",
                "logo": item.get("logo", ""),
                "applies": item.get("applies", 0),
            })
        
        return jobs