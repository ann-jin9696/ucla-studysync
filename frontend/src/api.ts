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

export type Profile = {
  courses: string[];
  study_goals: string[];
  pace_preference: string | null;
  study_style_preference: string | null;
  group_size_preference: string | null;
  preferred_study_time_tags: string[];
  has_basic_profile: boolean;
  is_complete: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type ProfileInput = {
  courses: string[];
  study_goals: string[];
  pace_preference: string | null;
  study_style_preference: string | null;
  group_size_preference: string | null;
  preferred_study_time_tags: string[];
};

export type WorkspaceDocument = {
  id: number;
  workspace_id: number;
  uploader_id: number;
  uploader_name: string;
  title: string;
  file_name: string;
  file_path: string;
  document_type: string;
  uploaded_at: string;
};

export type WorkspaceDocumentsResponse = {
  workspace_id: number;
  group_id: number;
  documents: WorkspaceDocument[];
};

export type MatchResult = {
  matchScore: number;
  matchedCourse: string;
  matchedSchedule: string;
  matchedPreference: string;
};

export type ActivityItem = {
  activityId: number;
  activityType: string;
  timestamp: string;
  description: string;
};

export type WorkspaceComment = {
  id: number;
  document_id: number;
  author_id: number;
  author_name: string;
  content: string;
  created_at: string;
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
  update(input: ProfileInput) {
    return request<Profile>('/api/profile/me', {
      method: 'PUT',
      body: JSON.stringify(input),
    });
  },
};

export const workspaceApi = {
  documentFileUrl(documentId: number) {
    return `${API_BASE_URL}/api/workspace/documents/${documentId}/file`;
  },
  listDocuments(search = '') {
    const params = new URLSearchParams();
    if (search.trim()) {
      params.set('search', search.trim());
    }
    const query = params.toString();
    return request<WorkspaceDocumentsResponse>(
      `/api/workspace/documents${query ? `?${query}` : ''}`,
    );
  },
  uploadDocument(input: { title: string; document_type: string; file: File }) {
    const formData = new FormData();
    formData.append('title', input.title);
    formData.append('document_type', input.document_type);
    formData.append('file', input.file);

    return request<WorkspaceDocument>('/api/workspace/documents', {
      method: 'POST',
      body: formData,
    });
  },
  listComments(documentId: number) {
    return request<WorkspaceComment[]>(
      `/api/workspace/documents/${documentId}/comments`,
    );
  },
  createComment(documentId: number, content: string) {
    return request<WorkspaceComment>(
      `/api/workspace/documents/${documentId}/comments`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      },
    );
  },
};


export const matchingApi = {
  listResults() {
    return request<MatchResult[]>('/api/matching/results');
  },
  listActivity() {
    return request<ActivityItem[]>('/api/matching/activity');
  },
};