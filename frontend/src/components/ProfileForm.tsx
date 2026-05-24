import { useEffect, useState } from 'react';
import { AutoComplete, Button, Card, Form, InputNumber, Select } from 'antd';
import {
  Books,
  CalendarBlank,
  Gauge,
  GraduationCap,
  PlusCircle,
  Trash,
  UsersThree,
} from '@phosphor-icons/react';
import type { Profile, ProfileCourseInput, ProfileInput } from '../api';
import { profileApi } from '../api';
import {
  COURSE_QUARTER_OPTIONS,
  PACE_OPTIONS,
  STUDY_GOAL_OPTIONS,
} from '../profileOptions';

type CourseFormValue = Partial<ProfileCourseInput>;

type ProfileFormValues = {
  courses?: CourseFormValue[];
};

type ProfileFormProps = {
  profile: Profile;
  onSubmit: (input: ProfileInput) => Promise<void>;
  submitting?: boolean;
  submitLabel: string;
};

const EMPTY_COURSE_ROW: CourseFormValue = {
  course_code: '',
  course_quarter: COURSE_QUARTER_OPTIONS[0].value,
  lecture_number: 1,
  study_goals: [],
  pace_preference: null,
  group_size_preference: null,
};

function profileToFormValues(profile: Profile): ProfileFormValues {
  return {
    courses:
      profile.courses.length > 0
        ? profile.courses.map((course) => ({
            course_code: course.course_code,
            course_quarter: course.course_quarter,
            lecture_number: course.lecture_number,
            study_goals: course.study_goals,
            pace_preference: course.pace_preference,
            group_size_preference: course.group_size_preference,
          }))
        : [EMPTY_COURSE_ROW],
  };
}

function formValuesToProfileInput(values: ProfileFormValues): ProfileInput {
  const courses: ProfileCourseInput[] = (values.courses ?? [])
    .filter((course) => course.course_code?.trim())
    .map((course) => ({
      course_code: course.course_code?.trim() ?? '',
      course_quarter: course.course_quarter ?? COURSE_QUARTER_OPTIONS[0].value,
      lecture_number: Number(course.lecture_number ?? 1),
      study_goals: course.study_goals ?? [],
      pace_preference: course.pace_preference ?? null,
      group_size_preference: course.group_size_preference ?? null,
    }));

  return { courses };
}

export function ProfileForm({
  profile,
  onSubmit,
  submitting = false,
  submitLabel,
}: ProfileFormProps) {
  const [form] = Form.useForm<ProfileFormValues>();
  const [courseCodeOptions, setCourseCodeOptions] = useState<
    { value: string; label: string }[]
  >([]);

  useEffect(() => {
    form.setFieldsValue(profileToFormValues(profile));
  }, [form, profile]);

  async function handleCourseCodeSearch(searchText: string) {
    try {
      const response = await profileApi.courseCodes(searchText);
      setCourseCodeOptions(
        response.options.map((courseCode) => ({
          value: courseCode,
          label: courseCode,
        })),
      );
    } catch {
      setCourseCodeOptions([]);
    }
  }

  async function handleFinish(values: ProfileFormValues) {
    await onSubmit(formValuesToProfileInput(values));
  }

  return (
    <Form
      className="profile-form"
      form={form}
      initialValues={profileToFormValues(profile)}
      layout="vertical"
      onFinish={handleFinish}
    >
      <Card className="profile-form-card profile-course-card">
        <div className="tool-card-heading">
          <Books size={24} weight="duotone" />
          <h2>Courses and matching preferences</h2>
        </div>
        <Form.List
          name="courses"
          rules={[
            {
              validator: async (_, courses) => {
                if (
                  Array.isArray(courses) &&
                  courses.some((course) => course?.course_code?.trim())
                ) {
                  return;
                }
                throw new Error('Add at least one course.');
              },
            },
          ]}
        >
          {(fields, { add, remove }, { errors }) => (
            <div className="course-list">
              {fields.map((field) => (
                <div className="course-row course-preference-row" key={field.key}>
                  <Form.Item
                    label="Course code"
                    name={[field.name, 'course_code']}
                    rules={[{ required: true, message: 'Add a course code.' }]}
                  >
                    <AutoComplete
                      filterOption={false}
                      onFocus={() => void handleCourseCodeSearch('')}
                      onSearch={(value) => void handleCourseCodeSearch(value)}
                      options={courseCodeOptions}
                      placeholder="CS35L"
                    />
                  </Form.Item>
                  <Form.Item
                    label="Quarter"
                    name={[field.name, 'course_quarter']}
                    rules={[{ required: true, message: 'Choose a quarter.' }]}
                  >
                    <Select options={COURSE_QUARTER_OPTIONS} />
                  </Form.Item>
                  <Form.Item
                    label="Lecture"
                    name={[field.name, 'lecture_number']}
                    rules={[{ required: true, message: 'Add a lecture number.' }]}
                  >
                    <InputNumber min={1} precision={0} />
                  </Form.Item>
                  <Form.Item
                    className="course-wide-field"
                    label={
                      <span className="profile-label-with-icon">
                        <GraduationCap size={16} weight="duotone" />
                        Study goals
                      </span>
                    }
                    name={[field.name, 'study_goals']}
                  >
                    <Select
                      mode="multiple"
                      options={STUDY_GOAL_OPTIONS}
                      placeholder="Choose one or more goals"
                    />
                  </Form.Item>
                  <Form.Item
                    label={
                      <span className="profile-label-with-icon">
                        <Gauge size={16} weight="duotone" />
                        Pace
                      </span>
                    }
                    name={[field.name, 'pace_preference']}
                  >
                    <Select allowClear options={PACE_OPTIONS} placeholder="Choose a pace" />
                  </Form.Item>
                  <Form.Item
                    label={
                      <span className="profile-label-with-icon">
                        <UsersThree size={16} weight="duotone" />
                        Group size
                      </span>
                    }
                    name={[field.name, 'group_size_preference']}
                  >
                    <InputNumber min={1} precision={0} placeholder="8" />
                  </Form.Item>
                  {fields.length > 1 && (
                    <Button
                      aria-label="Remove course"
                      className="course-remove-button"
                      icon={<Trash size={18} weight="bold" />}
                      onClick={() => remove(field.name)}
                    />
                  )}
                </div>
              ))}
              <Button
                icon={<PlusCircle size={18} weight="bold" />}
                onClick={() => add({ ...EMPTY_COURSE_ROW })}
                type="dashed"
              >
                Add course
              </Button>
              <Form.ErrorList errors={errors} />
            </div>
          )}
        </Form.List>
        <p className="profile-field-note">
          A course offering is the course code, quarter, and lecture number together.
          Group size is numeric: small is fewer than 5, medium is 5 to 10, and large
          is more than 10.
        </p>
      </Card>

      <div className="profile-actions">
        <Button
          className="profile-save-button"
          htmlType="submit"
          icon={<CalendarBlank size={18} weight="bold" />}
          loading={submitting}
          type="primary"
        >
          {submitLabel}
        </Button>
      </div>
    </Form>
  );
}
