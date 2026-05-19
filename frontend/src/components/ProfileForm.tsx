import { useEffect } from 'react';
import { Button, Card, Form, Select } from 'antd';
import { Books, Clock, Gauge, GraduationCap, UsersThree } from '@phosphor-icons/react';
import type { Profile, ProfileInput } from '../api';
import {
  GROUP_SIZE_OPTIONS,
  PACE_OPTIONS,
  PREFERRED_STUDY_TIME_OPTIONS,
  STUDY_GOAL_OPTIONS,
  STUDY_STYLE_OPTIONS,
} from '../profileOptions';

type ProfileFormValues = {
  courses?: string[];
  study_goals?: string[];
  pace_preference?: string | null;
  study_style_preference?: string | null;
  group_size_preference?: string | null;
  preferred_study_time_tags?: string[];
};

type ProfileFormProps = {
  profile: Profile;
  onSubmit: (input: ProfileInput) => Promise<void>;
  submitting?: boolean;
  submitLabel: string;
};

function profileToFormValues(profile: Profile): ProfileFormValues {
  return {
    courses: profile.courses,
    study_goals: profile.study_goals,
    pace_preference: profile.pace_preference,
    study_style_preference: profile.study_style_preference,
    group_size_preference: profile.group_size_preference,
    preferred_study_time_tags: profile.preferred_study_time_tags,
  };
}

function formValuesToProfileInput(values: ProfileFormValues): ProfileInput {
  return {
    courses: values.courses ?? [],
    study_goals: values.study_goals ?? [],
    pace_preference: values.pace_preference ?? null,
    study_style_preference: values.study_style_preference ?? null,
    group_size_preference: values.group_size_preference ?? null,
    preferred_study_time_tags: values.preferred_study_time_tags ?? [],
  };
}

export function ProfileForm({
  profile,
  onSubmit,
  submitting = false,
  submitLabel,
}: ProfileFormProps) {
  const [form] = Form.useForm<ProfileFormValues>();

  useEffect(() => {
    form.setFieldsValue(profileToFormValues(profile));
  }, [form, profile]);

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
      <Card className="profile-form-card">
        <div className="tool-card-heading">
          <Books size={24} weight="duotone" />
          <h2>Courses</h2>
        </div>
        <Form.Item
          label="Current courses"
          name="courses"
          rules={[
            {
              validator: (_, value) =>
                Array.isArray(value) && value.length > 0
                  ? Promise.resolve()
                  : Promise.reject(new Error('Add at least one course.')),
            },
          ]}
        >
          <Select
            mode="tags"
            placeholder="CS35L, MATH151A"
            tokenSeparators={[',']}
          />
        </Form.Item>
        <p className="profile-field-note">
          Use course codes like CS35L, MATH151A, or PHYSICS1A.
        </p>
      </Card>

      <Card className="profile-form-card">
        <div className="tool-card-heading">
          <GraduationCap size={24} weight="duotone" />
          <h2>Study goals</h2>
        </div>
        <Form.Item label="What do you need from a study group?" name="study_goals">
          <Select
            mode="multiple"
            options={STUDY_GOAL_OPTIONS}
            placeholder="Choose one or more goals"
          />
        </Form.Item>
      </Card>

      <Card className="profile-form-card">
        <div className="tool-card-heading">
          <Gauge size={24} weight="duotone" />
          <h2>Pace and style</h2>
        </div>
        <Form.Item label="Preferred pace" name="pace_preference">
          <Select allowClear options={PACE_OPTIONS} placeholder="Choose a pace" />
        </Form.Item>
        <Form.Item label="Study style" name="study_style_preference">
          <Select allowClear options={STUDY_STYLE_OPTIONS} placeholder="Choose a style" />
        </Form.Item>
      </Card>

      <Card className="profile-form-card">
        <div className="tool-card-heading">
          <UsersThree size={24} weight="duotone" />
          <h2>Group size</h2>
        </div>
        <Form.Item label="Optional group size preference" name="group_size_preference">
          <Select
            allowClear
            options={GROUP_SIZE_OPTIONS}
            placeholder="Choose a group size"
          />
        </Form.Item>
      </Card>

      <Card className="profile-form-card">
        <div className="tool-card-heading">
          <Clock size={24} weight="duotone" />
          <h2>Preferred study times</h2>
        </div>
        <Form.Item label="Optional lightweight time tags" name="preferred_study_time_tags">
          <Select
            mode="multiple"
            options={PREFERRED_STUDY_TIME_OPTIONS}
            placeholder="Weekday evenings, Flexible"
          />
        </Form.Item>
      </Card>

      <div className="profile-actions">
        <Button htmlType="submit" loading={submitting} type="primary">
          {submitLabel}
        </Button>
      </div>
    </Form>
  );
}
