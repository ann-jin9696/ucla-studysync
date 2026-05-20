from collections.abc import Iterable

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/matching", tags=["matching"])


def normalize_course_code(course_code: object) -> str:
    if not isinstance(course_code, str):
        return ""
    return "".join(course_code.upper().split())


def as_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [item for item in value if isinstance(item, str)]
    return []


def first_present(data: dict, keys: list[str]) -> object:
    for key in keys:
        if key in data:
            return data[key]
    return None


def calculate_matching_score(user_values: object, room_values: object) -> float:
    set_user, set_study_room = set(as_list(user_values)), set(as_list(room_values))

    intersection = set_user & set_study_room
    union = set_user | set_study_room

    if not union:
        return 0.0

    score = len(intersection) / len(union)
    return score * 100


def calculate_optional_preference_score(user_value: object, room_value: object) -> float:
    if user_value in (None, "", "no_preference"):
        return 100.0
    if room_value in (None, ""):
        return 0.0
    if room_value == "no_preference":
        return 100.0
    return 100.0 if user_value == room_value else 0.0


def calculate_required_preference_score(user_value: object, room_value: object) -> float:
    if user_value in (None, "") or room_value in (None, ""):
        return 0.0
    return 100.0 if user_value == room_value else 0.0


def get_final_score(user: dict, study_room: dict) -> float:
    user_courses = as_list(user.get("courses", []))
    room_course = study_room.get("course")
    normalized_user_courses = {
        normalized_course
        for normalized_course in (normalize_course_code(course) for course in user_courses)
        if normalized_course
    }

    if normalize_course_code(room_course) not in normalized_user_courses:
        return 0.0

    user_availability = first_present(
        user,
        ["preferred_study_time_tags", "availability"],
    )
    room_availability = first_present(
        study_room,
        ["preferred_study_time_tags", "availability"],
    )

    user_styles = first_present(
        user,
        ["study_style_preference", "study_styles"],
    )
    room_styles = first_present(
        study_room,
        ["study_style_preference", "study_styles"],
    )

    user_goals = user.get("study_goals", [])
    room_goals = study_room.get("study_goals", [])

    availability_score = calculate_matching_score(user_availability, room_availability)
    styles_score = calculate_matching_score(user_styles, room_styles)
    goals_score = calculate_matching_score(user_goals, room_goals)

    user_pace = first_present(user, ["pace_preference", "pace"])
    room_pace = first_present(study_room, ["pace_preference", "pace"])

    pace_score = calculate_required_preference_score(user_pace, room_pace)

    user_size_preference = first_present(
        user,
        ["group_size_preference", "size_preference"],
    )
    room_size = first_present(study_room, ["group_size_preference", "size"])

    size_score = calculate_optional_preference_score(user_size_preference, room_size)

    weights = {
        "availability": 0.15,
        "study_styles": 0.35,
        "study_goals": 0.25,
        "pace": 0.15,
        "room_size": 0.10,
    }

    final_score = (
        (weights["availability"] * availability_score)
        + (weights["study_styles"] * styles_score)
        + (weights["study_goals"] * goals_score)
        + (weights["pace"] * pace_score)
        + (weights["room_size"] * size_score)
    )

    return round(final_score, 2)


def search_rooms(user: dict, all_rooms: list[dict]) -> list[dict]:
    results = []
    for room in all_rooms:
        score = get_final_score(user, room)
        if score > 0:
            match_entry = room.copy()
            match_entry["match_score"] = score
            results.append(match_entry)

    return sorted(results, key=lambda x: x["match_score"], reverse=True)

MOCK_ROOMS = [
    {
        "id": 1,
        "course": "MATH131A",
        "preferred_study_time_tags": ["weekday_mornings"],
        "study_style_preference": "quiet_parallel",
        "study_goals": ["homework_help"],
        "pace_preference": "moderate",
        "group_size_preference": "small_group",
    },
    {
        "id": 2,
        "course": "CS35L",
        "preferred_study_time_tags": ["weekday_evenings"],
        "study_style_preference": "discussion_based",
        "study_goals": ["project_work"],
        "pace_preference": "intensive",
        "group_size_preference": "large_group",
    },
]


@router.post("/search")
async def handle_search(search_criteria: dict = Body(...)):
    results = search_rooms(search_criteria, MOCK_ROOMS)
    return {"results": results}
