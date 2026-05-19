from fastapi import APIRouter, Body
from .matching import search_rooms

router = APIRouter(prefix="/api/matching", tags=["matching"])

MOCK_ROOMS = [
    {"id": 1, "course": "Math131A", "availability": ["M10"], "preferences": ["Quiet"]},
    {"id": 2, "course": "CS35L", "availability": ["T15"], "preferences": ["Group"]}
]

@router.post("/search")
async def handle_search(search_criteria: dict = Body(...)):
    results = search_rooms(search_criteria, MOCK_ROOMS)
    return {"results": results}

