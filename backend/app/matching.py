def calculate_matching_score(user_a_courses, user_b_courses):
    set_a, set_b = set(user_a_courses), set(user_b_courses)

    intersection = set_a & set_b
    union = set_a | set_b

    if not union:
        return 0.0

    score = len(intersection) / len(union)
    return round(score * 100, 2)
