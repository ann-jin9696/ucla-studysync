import type { Profile } from './api';

export const EMPTY_PROFILE: Profile = {
  courses: [],
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

const TERMS = ['Winter', 'Spring', 'Summer', 'Fall'];

export function getCourseQuarterOptions(currentDate = new Date()) {
  const finalYear = currentDate.getFullYear() + 2;
  const options = [];
  for (let year = 2026; year <= finalYear; year += 1) {
    for (const term of TERMS) {
      if (year === 2026 && TERMS.indexOf(term) < TERMS.indexOf('Spring')) {
        continue;
      }
      options.push({ label: `${term} ${year}`, value: `${term} ${year}` });
    }
  }
  return options;
}

export const COURSE_QUARTER_OPTIONS = getCourseQuarterOptions();

export function getMissingProfileSections(profile: Profile | null) {
  const missingSections = [];
  if (!profile?.courses.length) {
    missingSections.push('courses');
    return missingSections;
  }
  if (profile.courses.some((course) => course.study_goals.length === 0)) {
    missingSections.push('study goals');
  }
  if (profile.courses.some((course) => !course.pace_preference)) {
    missingSections.push('pace preference');
  }
  return missingSections;
}
