def calculate_matching_score(user_a, user_b):
    # Use Jaccard Similarity to get scores

    set_a, set_b = set(user_a), set(user_b)

    intersection = set_a & set_b
    union = set_a | set_b

    if not union:
        return 0.0

    score = len(intersection) / len(union)
    return round(score * 100, 2)

def get_final_score(user_a, user_b):
    # Use weights on more important matching criteria
    
    weight_course, weight_availability, weight_preferences = 0.6, 0.3, 0.1

    course_score = calculate_matching_score(user_a["courses"], user_b["courses"])
    availability_score = calculate_matching_score(user_a["availability"], user_b["availability"])
    preferences_score = calculate_matching_score(user_a["preferences"], user_b["preferences"])

    print(f"Course: {weight_course * course_score}")
    print(f"Avail: {weight_availability * availability_score}")
    print(f"Pref: {weight_preferences * preferences_score}")

    final_score = (weight_course * course_score) + (weight_availability * availability_score) + (weight_preferences * preferences_score)

    return round(final_score, 2)