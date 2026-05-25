export type User = {
  id: number;
  full_name: string;
  email: string;
  created_at: string;
};

export type AuthResponse = {
  user: User;
};

export type SignupInput = {
  full_name: string;
  email: string;
  password: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type ProfileCourseInput = {
  course_code: string;
  course_quarter: string;
  lecture_number: number;
  study_goals: string[];
  pace_preference: string | null;
  group_size_preference: number | null;
};

export type ProfileCourse = ProfileCourseInput & {
  user_course_id: number;
  course_id: number;
};

export type Profile = {
  courses: ProfileCourse[];
  has_basic_profile: boolean;
  is_complete: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ProfileInput = {
  courses: ProfileCourseInput[];
};

export type CourseCodeOptionsResponse = {
  options: string[];
};

export type Group = {
  id: number;
  name: string;
  course_id: number;
  course_code: string;
  course_quarter: string;
  lecture_number: number;
  created_by_user_id: number;
  member_count: number;
  created_at: string;
  updated_at: string;
};

export type StudyGoalSummary = {
  value: string;
  count: number;
};

export type GroupMember = {
  user_id: number;
  full_name: string;
  is_owner: boolean;
  study_goals: string[];
  pace_preference: string | null;
  group_size_preference: number | null;
  joined_at: string;
};

export type GroupDetail = Group & {
  owner_name: string;
  top_study_goals: StudyGoalSummary[];
  average_pace_preference: string | null;
  average_pace_score: number | null;
  group_size_bucket: string;
  members: GroupMember[];
};

export type GroupDirectoryEntry = Group & {
  owner_name: string;
  top_study_goals: StudyGoalSummary[];
  average_pace_preference: string | null;
  average_pace_score: number | null;
  group_size_bucket: string;
  matches_preferred_group_size: boolean;
  is_member: boolean;
  is_owner: boolean;
  pending_request_id: number | null;
  pending_applicant_count: number;
};

export type JoinRequest = {
  id: number;
  group_id: number;
  user_id: number;
  user_name: string;
  status: string;
  created_at: string;
  decided_at: string | null;
};

export type PendingApplication = {
  id: number;
  group_id: number;
  group_name: string;
  course_code: string;
  user_id: number;
  user_name: string;
  created_at: string;
};

export type GroupDocument = {
  id: number;
  group_id: number;
  uploader_id: number;
  uploader_name: string;
  title: string;
  file_name: string;
  file_path: string;
  document_type: string;
  uploaded_at: string;
};

export type GroupDocumentsResponse = {
  group_id: number;
  documents: GroupDocument[];
};

export type GroupComment = {
  id: number;
  document_id: number;
  author_id: number;
  author_name: string;
  content: string;
  created_at: string;
};

export type GroupActivity = {
  id: string;
  activity_type: 'document_uploaded' | 'comment_added';
  group_id: number;
  group_name: string;
  course_code: string;
  document_id: number;
  document_title: string;
  actor_id: number;
  actor_name: string;
  occurred_at: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? options.headers
    : {
        'Content-Type': 'application/json',
        ...options.headers,
      };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = 'Something went wrong. Please try again.';
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') {
        message = body.detail;
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = body.detail[0].msg;
      }
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const authApi = {
  signup(input: SignupInput) {
    return request<AuthResponse>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },
  login(input: LoginInput) {
    return request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },
  logout() {
    return request<void>('/api/auth/logout', { method: 'POST' });
  },
  me() {
    return request<AuthResponse>('/api/auth/me');
  },
};

export const profileApi = {
  me() {
    return request<Profile>('/api/profile/me');
  },
  courseQuarters() {
    return request<{ options: string[] }>('/api/profile/course-quarters');
  },
  courseCodes(search = '') {
    const params = new URLSearchParams();
    if (search.trim()) {
      params.set('search', search.trim());
    }
    const query = params.toString();
    return request<CourseCodeOptionsResponse>(
      `/api/profile/course-codes${query ? `?${query}` : ''}`,
    );
  },
  update(input: ProfileInput) {
    return request<Profile>('/api/profile/me', {
      method: 'PUT',
      body: JSON.stringify(input),
    });
  },
};

export const groupApi = {
  listMyGroups() {
    return request<Group[]>('/api/groups');
  },
  getDetail(groupId: number) {
    return request<GroupDetail>(`/api/groups/${groupId}`);
  },
  listActivity(limit = 8) {
    const params = new URLSearchParams({ limit: String(limit) });
    return request<GroupActivity[]>(`/api/groups/activity?${params.toString()}`);
  },
  listPendingApplications() {
    return request<PendingApplication[]>('/api/groups/join-requests/pending');
  },
  create(input: { user_course_id: number; name?: string }) {
    return request<Group>('/api/groups', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },
  apply(groupId: number) {
    return request<JoinRequest>(`/api/groups/${groupId}/join-requests`, {
      method: 'POST',
    });
  },
  leave(groupId: number) {
    return request<Group>(`/api/groups/${groupId}/membership`, {
      method: 'DELETE',
    });
  },
  listJoinRequests(groupId: number) {
    return request<JoinRequest[]>(`/api/groups/${groupId}/join-requests`);
  },
  approveJoinRequest(groupId: number, requestId: number) {
    return request<JoinRequest>(
      `/api/groups/${groupId}/join-requests/${requestId}/approve`,
      { method: 'POST' },
    );
  },
  rejectJoinRequest(groupId: number, requestId: number) {
    return request<JoinRequest>(
      `/api/groups/${groupId}/join-requests/${requestId}/reject`,
      { method: 'POST' },
    );
  },
  withdrawJoinRequest(groupId: number, requestId: number) {
    return request<JoinRequest>(`/api/groups/${groupId}/join-requests/${requestId}`, {
      method: 'DELETE',
    });
  },
  documentFileUrl(groupId: number, documentId: number) {
    return `${API_BASE_URL}/api/groups/${groupId}/documents/${documentId}/file`;
  },
  listDocuments(groupId: number, search = '') {
    const params = new URLSearchParams();
    if (search.trim()) {
      params.set('search', search.trim());
    }
    const query = params.toString();
    return request<GroupDocumentsResponse>(
      `/api/groups/${groupId}/documents${query ? `?${query}` : ''}`,
    );
  },
  uploadDocument(input: {
    group_id: number;
    title: string;
    document_type: string;
    file: File;
  }) {
    const formData = new FormData();
    formData.append('title', input.title);
    formData.append('document_type', input.document_type);
    formData.append('file', input.file);

    return request<GroupDocument>(`/api/groups/${input.group_id}/documents`, {
      method: 'POST',
      body: formData,
    });
  },
  listComments(groupId: number, documentId: number) {
    return request<GroupComment[]>(
      `/api/groups/${groupId}/documents/${documentId}/comments`,
    );
  },
  createComment(groupId: number, documentId: number, content: string) {
    return request<GroupComment>(
      `/api/groups/${groupId}/documents/${documentId}/comments`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      },
    );
  },
};

export const matchingApi = {
  listGroups(
    userCourseId: number,
    filters: {
      studyGoals?: string[];
      pacePreference?: string | null;
      groupSize?: string | null;
    } = {},
  ) {
    const params = new URLSearchParams({ user_course_id: String(userCourseId) });
    for (const goal of filters.studyGoals ?? []) {
      params.append('study_goal', goal);
    }
    if (filters.pacePreference) {
      params.set('pace_preference', filters.pacePreference);
    }
    if (filters.groupSize) {
      params.set('group_size', filters.groupSize);
    }
    return request<GroupDirectoryEntry[]>(`/api/matching/groups?${params.toString()}`);
  },
};
