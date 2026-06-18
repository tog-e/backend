"""
Google Places API-с Улаанбаатарын activities татах
"""
import os
import httpx
from fastapi import APIRouter

router = APIRouter()

ULAANBAATAR = "47.9077,106.8832"

PLACE_TYPES = [
    ("cafe", "☕ Кофе шоп", "#F472B6"),
    ("restaurant", "🍜 Ресторан", "#FBBF24"),
    ("movie_theater", "🎭 Кино театр", "#A78BFA"),
    ("bowling_alley", "🎳 Боулинг", "#34D399"),
    ("park", "🌿 Парк", "#34D399"),
    ("gym", "🏋️ Спорт заал", "#60A5FA"),
    ("museum", "🏛️ Музей", "#F87171"),
    ("shopping_mall", "🛍️ Худалдааны төв", "#FBBF24"),
]

@router.get("/")
async def get_places(category: str = "all", radius: int = 5000):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return {"places": [], "error": "API key байхгүй"}
    
    all_places = []
    
    types_to_fetch = PLACE_TYPES if category == "all" else [p for p in PLACE_TYPES if p[0] == category]
    
    async with httpx.AsyncClient() as client:
        for place_type, label, color in types_to_fetch[:3]:
            try:
                res = await client.get(
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                    params={
                        "location": ULAANBAATAR,
                        "radius": radius,
                        "type": place_type,
                        "language": "mn",
                        "key": api_key,
                    },
                    timeout=10
                )
                data = res.json()
                
                for place in data.get("results", [])[:5]:
                    all_places.append({
                        "id": place.get("place_id"),
                        "name": place.get("name"),
                        "category": label,
                        "color": color,
                        "address": place.get("vicinity", "Улаанбаатар"),
                        "rating": place.get("rating", 0),
                        "user_ratings": place.get("user_ratings_total", 0),
                        "lat": place.get("geometry", {}).get("location", {}).get("lat"),
                        "lng": place.get("geometry", {}).get("location", {}).get("lng"),
                        "open_now": place.get("opening_hours", {}).get("open_now"),
                        "photo": f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={place['photos'][0]['photo_reference']}&key={api_key}" if place.get("photos") else None,
                    })
            except Exception as e:
                continue
    
    return {"places": all_places, "total": len(all_places)}


@router.get("/categories")
async def get_categories():
    return {"categories": [{"type": t, "label": l, "color": c} for t, l, c in PLACE_TYPES]}