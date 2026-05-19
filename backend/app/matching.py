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
    return round(score * 100, 2)

def get_final_score(user, study_room):
    # Filter out rooms that the user doesn't want
    
    user_courses = user.get("courses", [])
    room_course = study_room.get("course")

    if room_course not in user_courses:
        return 0.0

    weight_availability, weight_preferences = 0.7, 0.3

    availability_score = calculate_matching_score(user.get("availability", []), study_room.get("availability", []))
    preferences_score = calculate_matching_score(user.get("preferences", []), study_room.get("preferences", []))

    final_score = (weight_availability * availability_score) + (weight_preferences * preferences_score)

    return round(final_score, 2)

def search_rooms(user, all_rooms):
    """
    Processes all rooms, filters them, and returns sorted list
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