from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/matching", tags=["matching"])


def calculate_matching_score(user, study_room):
    """
    Use Jaccard Similarity calculations on the sets of strings to get scores
    """

    set_user, set_study_room = set(user), set(study_room)

    intersection = set_user & set_study_room
    union = set_user | set_study_room

    if not union:
        return 0.0

    score = len(intersection) / len(union)
    return score * 100

def get_final_score(user, study_room):
    # Filter out rooms that the user doesn't want
    
    user_courses = user.get("courses", [])
    room_course = study_room.get("course")

    if room_course not in user_courses:
        return 0.0

    user_avail = user.get("availability", [])
    room_avail = study_room.get("availability", [])

    user_styles = user.get("study_styles", [])
    room_styles = study_room.get("study_styles", [])

    user_goals = user.get("study_goals", [])
    room_goals = study_room.get("study_goals", [])

    availability_score = calculate_matching_score(user_avail, room_avail)
    styles_score = calculate_matching_score(user_styles, room_styles)
    goals_score = calculate_matching_score(user_goals, room_goals)

    # Users can pick one pace and rooms have one pace
    user_pace = user.get("pace")
    room_pace = study_room.get("pace")

    pace_score = 100.0 if (user_pace == room_pace and user_pace is not None) else 0.0

    # Users have one size preference and rooms have a single size determined when created
    user_size_preference = user.get("size_preference")
    room_size = study_room.get("size")

    if user_size_preference == "no_preference" or room_size == "no_preference":
        size_score = 100.0
    else:
        size_score = 100.0 if (user_size_preference == room_size and user_size_preference is not None) else 0.0

    # we focus more on group chemistry for scoring
    weights = {
        "availability": 0.15,
        "study_styles": 0.35,
        "study_goals": 0.25,
        "pace": 0.15,
        "room_size": 0.10
    }

    final_score = (
        (weights["availability"] * availability_score) 
        + (weights["study_styles"] * styles_score)
        + (weights["study_goals"] * goals_score)
        + (weights["pace"] * pace_score)
        + (weights["room_size"] * size_score)
    )

    return round(final_score, 2)

def search_rooms(user, all_rooms):
    """
    If a user wants to find multiple courses, processes all rooms, filters them, and returns sorted list
    """
    results = []
    for room in all_rooms:
        score = get_final_score(user, room)
        #only show rooms user wants
        if score > 0:
            match_entry = room.copy()
            match_entry["match_score"] = score
            results.append(match_entry)

    return sorted(results, key=lambda x: x["match_score"], reverse=True)

MOCK_ROOMS = [
    {"id": 1, "course": "Math131A", "availability": ["M10"], "preferences": ["Quiet"]},
    {"id": 2, "course": "CS35L", "availability": ["T15"], "preferences": ["Group"]}
]

@router.post("/search")
async def handle_search(search_criteria: dict = Body(...)):
    results = search_rooms(search_criteria, MOCK_ROOMS)
    return {"results": results}
