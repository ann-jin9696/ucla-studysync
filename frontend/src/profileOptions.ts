import type { Profile } from './api';

export const EMPTY_PROFILE: Profile = {
  courses: [],
  study_goals: [],
  pace_preference: null,
  study_style_preference: null,
  group_size_preference: null,
  preferred_study_time_tags: [],
  has_basic_profile: false,
  is_complete: false,
  created_at: null,
  updated_at: null,
};

export const STUDY_GOAL_OPTIONS = [
  { label: 'Homework help', value: 'homework_help' },
  { label: 'Exam prep', value: 'exam_prep' },
  { label: 'Project work', value: 'project_work' },
  { label: 'Concept review', value: 'concept_review' },
  { label: 'Notes sharing', value: 'notes_sharing' },
];

export const PACE_OPTIONS = [
  { label: 'Relaxed', value: 'relaxed' },
  { label: 'Moderate', value: 'moderate' },
  { label: 'Intensive', value: 'intensive' },
];

export const STUDY_STYLE_OPTIONS = [
  { label: 'Quiet parallel work', value: 'quiet_parallel' },
  { label: 'Discussion based', value: 'discussion_based' },
  { label: 'Problem solving', value: 'problem_solving' },
  { label: 'Teaching each other', value: 'teaching_each_other' },
];

export const GROUP_SIZE_OPTIONS = [
  { label: 'Pair', value: 'pair' },
  { label: 'Small group', value: 'small_group' },
  { label: 'Large group', value: 'large_group' },
  { label: 'No preference', value: 'no_preference' },
];

export const PREFERRED_STUDY_TIME_OPTIONS = [
  { label: 'Weekday mornings', value: 'weekday_mornings' },
  { label: 'Weekday afternoons', value: 'weekday_afternoons' },
  { label: 'Weekday evenings', value: 'weekday_evenings' },
  { label: 'Weekend mornings', value: 'weekend_mornings' },
  { label: 'Weekend afternoons', value: 'weekend_afternoons' },
  { label: 'Weekend evenings', value: 'weekend_evenings' },
  { label: 'Late nights', value: 'late_nights' },
  { label: 'Flexible', value: 'flexible' },
];

export function getMissingProfileSections(profile: Profile | null) {
  const missingSections = [];
  if (!profile?.courses.length) {
    missingSections.push('courses');
  }
  if (!profile?.study_goals.length) {
    missingSections.push('study goals');
  }
  if (!profile?.pace_preference) {
    missingSections.push('pace preference');
  }
  if (!profile?.study_style_preference) {
    missingSections.push('study style preference');
  }
  return missingSections;
}
