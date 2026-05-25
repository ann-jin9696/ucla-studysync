import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';
import {
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Spin,
  Tag,
  message,
} from 'antd';
import {
  ChatCircleText,
  FileArrowUp,
  Info,
  MagnifyingGlass,
  NotePencil,
  PaperPlaneTilt,
  Sparkle,
  Trash,
  UsersThree,
} from '@phosphor-icons/react';
import type { Group, GroupDetail, GroupDocument } from '../api';
import { groupApi } from '../api';
import { parseApiTimestamp } from '../dateTime';
import { PACE_OPTIONS, STUDY_GOAL_OPTIONS } from '../profileOptions';

export type WorkspaceModuleMode = 'workspace' | 'discussion';

type UploadFormValues = {
  title: string;
  document_type: string;
};

const DOCUMENT_TYPES = [
  { label: 'Notes', value: 'notes' },
  { label: 'Slides', value: 'slides' },
  { label: 'Worksheet', value: 'worksheet' },
  { label: 'Review Guide', value: 'review' },
  { label: 'Other', value: 'other' },
];
const SUPPORTED_UPLOAD_EXTENSIONS = ['.pdf', '.png', '.jpg', '.txt', '.md'];
const SUPPORTED_UPLOAD_ACCEPT = SUPPORTED_UPLOAD_EXTENSIONS.join(',');
const SUPPORTED_UPLOAD_LABEL = 'PDF, PNG, JPG, TXT, or MD';
const MAX_UPLOAD_FILE_MB = 50;

const STUDY_GOAL_LABELS = new Map(
  STUDY_GOAL_OPTIONS.map((option) => [option.value, option.label]),
);
const PACE_LABELS = new Map(PACE_OPTIONS.map((option) => [option.value, option.label]));

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parseApiTimestamp(value));
}

function formatGroupMeta(group: Group) {
  return `${group.course_code} ${group.course_quarter} Lec ${group.lecture_number}`;
}

function formatGoal(value: string) {
  return STUDY_GOAL_LABELS.get(value) ?? value;
}

function formatPace(value: string | null) {
  if (!value) {
    return 'No pace yet';
  }
  return PACE_LABELS.get(value) ?? value;
}

function formatGroupSizeBucket(value: string) {
  if (value === 'small') {
    return 'Small (<5)';
  }
  if (value === 'medium') {
    return 'Medium (5-10)';
  }
  if (value === 'large') {
    return 'Large (>10)';
  }
  return 'Unknown size';
}

function documentIndexTag(document: GroupDocument) {
  if (document.index_status === 'ready') {
    return { color: 'cyan', label: 'Ready' };
  }
  if (document.index_status === 'indexing') {
    return { color: 'gold', label: 'Indexing' };
  }
  return { color: 'red', label: 'Q&A failed' };
}

function getFileExtension(fileName: string) {
  const extensionStart = fileName.lastIndexOf('.');
  return extensionStart >= 0 ? fileName.slice(extensionStart).toLowerCase() : '';
}

function isSupportedUploadFile(file: File) {
  return SUPPORTED_UPLOAD_EXTENSIONS.includes(getFileExtension(file.name));
}

function isImageDocument(document: GroupDocument) {
  return /\.(jpg|png)$/i.test(document.file_name);
}

function isPdfDocument(document: GroupDocument) {
  return /\.pdf$/i.test(document.file_name);
}

function isPlainTextDocument(document: GroupDocument) {
  return /\.txt$/i.test(document.file_name);
}

function isMarkdownDocument(document: GroupDocument) {
  return /\.md$/i.test(document.file_name);
}

function isTextPreviewDocument(document: GroupDocument) {
  return isPlainTextDocument(document) || isMarkdownDocument(document);
}

function classNames(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(' ');
}

function getActivityTargetId(activityId: string | null | undefined, prefix: string) {
  const match = activityId?.match(new RegExp(`^${prefix}-(\\d+)$`));
  return match ? Number(match[1]) : null;
}

function DocumentTags({ document }: { document: GroupDocument }) {
  const indexTag = documentIndexTag(document);
  return (
    <div className="document-row-tags">
      <Tag color="green">{document.document_type}</Tag>
      <Tag color={indexTag.color}>{indexTag.label}</Tag>
    </div>
  );
}

function DocumentAiSummary({ summary }: { summary: string }) {
  return (
    <span className="document-ai-summary">
      <span className="document-ai-label">
        <Sparkle size={13} weight="fill" />
        AI
      </span>
      <em>{summary}</em>
    </span>
  );
}

function renderHeading(level: number, content: string, key: string) {
  if (level === 1) {
    return <h1 key={key}>{content}</h1>;
  }
  if (level === 2) {
    return <h2 key={key}>{content}</h2>;
  }
  return <h3 key={key}>{content}</h3>;
}

function renderMarkdownBlocks(markdown: string) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    const blockKey = `markdown-block-${index}`;

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith('```')) {
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push(
        <pre key={blockKey}>
          <code>{codeLines.join('\n')}</code>
        </pre>,
      );
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      blocks.push(renderHeading(heading[1].length, heading[2], blockKey));
      index += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*]\s+/, ''));
        index += 1;
      }
      blocks.push(
        <ul key={blockKey}>
          {items.map((item, itemIndex) => (
            <li key={`${blockKey}-${itemIndex}`}>{item}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ''));
        index += 1;
      }
      blocks.push(
        <ol key={blockKey}>
          {items.map((item, itemIndex) => (
            <li key={`${blockKey}-${itemIndex}`}>{item}</li>
          ))}
        </ol>,
      );
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ''));
        index += 1;
      }
      blocks.push(<blockquote key={blockKey}>{quoteLines.join(' ')}</blockquote>);
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !/^(#{1,3})\s+/.test(lines[index].trim()) &&
      !/^[-*]\s+/.test(lines[index].trim()) &&
      !/^\d+\.\s+/.test(lines[index].trim()) &&
      !/^>\s?/.test(lines[index].trim()) &&
      !lines[index].trim().startsWith('```')
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push(<p key={blockKey}>{paragraphLines.join(' ')}</p>);
  }

  return blocks.length > 0 ? blocks : <p>No preview content available.</p>;
}

type WorkspaceModuleProps = {
  mode: WorkspaceModuleMode;
  initialGroupId?: number | null;
  initialDocumentId?: number | null;
  focusActivityId?: string | null;
  focusRequestId?: number;
  onActivityChange?: () => void;
};

export function WorkspaceModule({
  mode,
  initialGroupId = null,
  initialDocumentId = null,
  focusActivityId = null,
  focusRequestId = 0,
  onActivityChange,
}: WorkspaceModuleProps) {
  const shellRef = useRef<HTMLElement | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const [uploadForm] = Form.useForm<UploadFormValues>();
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<GroupDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [comments, setComments] = useState<
    Awaited<ReturnType<typeof groupApi.listComments>>
  >([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [commentText, setCommentText] = useState('');
  const [qaQuestion, setQaQuestion] = useState('');
  const [qaAnswer, setQaAnswer] = useState<Awaited<
    ReturnType<typeof groupApi.askDocuments>
  > | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [loadingComments, setLoadingComments] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [postingComment, setPostingComment] = useState(false);
  const [askingDocuments, setAskingDocuments] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<GroupDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [groupDetailOpen, setGroupDetailOpen] = useState(false);
  const [selectedGroupDetail, setSelectedGroupDetail] = useState<GroupDetail | null>(null);
  const [loadingGroupDetail, setLoadingGroupDetail] = useState(false);

  useEffect(() => {
    if (!previewDocument) {
      setPreviewUrl(null);
      setPreviewText(null);
      setPreviewError(null);
      setLoadingPreview(false);
      return;
    }
    const currentPreviewDocument = previewDocument;
    const fileUrl = groupApi.documentFileUrl(
      currentPreviewDocument.group_id,
      currentPreviewDocument.id,
    );
    const controller = new AbortController();

    setPreviewUrl(fileUrl);
    setPreviewText(null);
    setPreviewError(null);
    setLoadingPreview(isTextPreviewDocument(currentPreviewDocument));
    async function loadPreview() {
      if (!isTextPreviewDocument(currentPreviewDocument)) {
        return;
      }
      try {
        const response = await fetch(fileUrl, {
          credentials: 'include',
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Failed to load file: ${response.status}`);
        }

        setPreviewText(await response.text());
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        console.error('File preview failed:', error);
        setPreviewError('Could not load this file preview.');
      } finally {
        setLoadingPreview(false);
      }
    }

    void loadPreview();

    return () => {
      controller.abort();
    };
  }, [previewDocument]);

  const selectedGroup = useMemo(
    () => groups.find((group) => group.id === selectedGroupId) ?? null,
    [groups, selectedGroupId],
  );

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );
  const moduleTitle = mode === 'workspace' ? 'Shared workspaces' : 'Group discussion';
  const moduleDescription =
    mode === 'workspace'
      ? 'Choose a group workspace and manage its shared files.'
      : 'Choose a group workspace and keep comments beside its materials.';
  const focusedCommentId = useMemo(
    () => getActivityTargetId(focusActivityId, 'comment'),
    [focusActivityId],
  );
  const focusedDocumentId = useMemo(
    () =>
      getActivityTargetId(focusActivityId, 'document') ??
      (focusActivityId ? initialDocumentId : null),
    [focusActivityId, initialDocumentId],
  );

  async function loadGroups() {
    setLoadingGroups(true);
    try {
      const response = await groupApi.listMyGroups();
      setGroups(response);
      setSelectedGroupId((currentId) => {
        if (initialGroupId && response.some((group) => group.id === initialGroupId)) {
          return initialGroupId;
        }
        if (response.some((group) => group.id === currentId)) {
          return currentId;
        }
        return response[0]?.id ?? null;
      });
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not load groups.');
    } finally {
      setLoadingGroups(false);
    }
  }

  async function loadDocuments(
    nextSearch = searchQuery,
    groupId = selectedGroupId,
    options: { showLoading?: boolean } = {},
  ) {
    if (!groupId) {
      setDocuments([]);
      setSelectedDocumentId(null);
      return;
    }

    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setLoadingDocuments(true);
    }
    try {
      const response = await groupApi.listDocuments(groupId, nextSearch);
      setDocuments(response.documents);
      setSelectedDocumentId((currentId) => {
        if (
          initialDocumentId &&
          response.documents.some((document) => document.id === initialDocumentId)
        ) {
          return initialDocumentId;
        }
        if (response.documents.some((document) => document.id === currentId)) {
          return currentId;
        }
        return response.documents[0]?.id ?? null;
      });
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not load documents.');
    } finally {
      if (showLoading) {
        setLoadingDocuments(false);
      }
    }
  }

  async function openGroupDetail() {
    if (!selectedGroupId) {
      return;
    }

    setGroupDetailOpen(true);
    setLoadingGroupDetail(true);
    try {
      setSelectedGroupDetail(await groupApi.getDetail(selectedGroupId));
    } catch (error) {
      messageApi.error(
        error instanceof Error ? error.message : 'Could not load group info.',
      );
    } finally {
      setLoadingGroupDetail(false);
    }
  }

  async function handleUpload(values: UploadFormValues) {
    if (!selectedGroupId) {
      messageApi.warning('Choose a group first.');
      return;
    }
    if (!uploadFile) {
      messageApi.warning('Choose a file to upload.');
      return;
    }

    setUploading(true);
    try {
      const uploaded = await groupApi.uploadDocument({
        group_id: selectedGroupId,
        title: values.title,
        document_type: values.document_type,
        file: uploadFile,
      });
      messageApi.success('Document uploaded. Q&A indexing will continue in the background.');
      uploadForm.resetFields();
      setUploadFile(null);
      setFileInputKey((key) => key + 1);
      await loadDocuments(searchQuery, selectedGroupId);
      setSelectedDocumentId(uploaded.id);
      onActivityChange?.();
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not upload document.');
    } finally {
      setUploading(false);
    }
  }

  function handleDeleteDocument(documentToDelete: GroupDocument) {
    Modal.confirm({
      title: `Delete ${documentToDelete.title}?`,
      content: 'This removes the shared file and its comments from the group.',
      okText: 'Delete',
      okButtonProps: { danger: true },
      async onOk() {
        try {
          await groupApi.deleteDocument(documentToDelete.group_id, documentToDelete.id);
          messageApi.success('Document deleted.');
          setPreviewDocument((currentDocument) =>
            currentDocument?.id === documentToDelete.id ? null : currentDocument,
          );
          setComments((currentComments) =>
            selectedDocumentId === documentToDelete.id ? [] : currentComments,
          );
          await loadDocuments(searchQuery, documentToDelete.group_id);
          onActivityChange?.();
        } catch (error) {
          messageApi.error(
            error instanceof Error ? error.message : 'Could not delete document.',
          );
        }
      },
    });
  }

  async function handlePostComment() {
    if (!selectedGroupId || !selectedDocument || !commentText.trim()) {
      return;
    }

    setPostingComment(true);
    try {
      const created = await groupApi.createComment(
        selectedGroupId,
        selectedDocument.id,
        commentText,
      );
      setComments((currentComments) => [...currentComments, created]);
      setCommentText('');
      onActivityChange?.();
      messageApi.success('Comment added.');
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not add comment.');
    } finally {
      setPostingComment(false);
    }
  }

  async function handleAskDocuments() {
    if (!selectedGroupId || !qaQuestion.trim()) {
      return;
    }

    setAskingDocuments(true);
    try {
      setQaAnswer(await groupApi.askDocuments(selectedGroupId, qaQuestion));
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not ask documents.');
    } finally {
      setAskingDocuments(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    if (nextFile && !isSupportedUploadFile(nextFile)) {
      setUploadFile(null);
      event.target.value = '';
      messageApi.warning(`Choose a ${SUPPORTED_UPLOAD_LABEL} file.`);
      return;
    }
    if (nextFile && nextFile.size > MAX_UPLOAD_FILE_MB * 1024 * 1024) {
      setUploadFile(null);
      event.target.value = '';
      messageApi.warning(`Choose a file ${MAX_UPLOAD_FILE_MB} MB or smaller.`);
      return;
    }
    setUploadFile(nextFile);
  }

  useEffect(() => {
    void loadGroups();
  }, []);

  useEffect(() => {
    if (initialGroupId && groups.some((group) => group.id === initialGroupId)) {
      setSelectedGroupId(initialGroupId);
    }
  }, [initialGroupId, groups]);

  useEffect(() => {
    if (
      initialDocumentId &&
      documents.some((document) => document.id === initialDocumentId)
    ) {
      setSelectedDocumentId(initialDocumentId);
    }
  }, [initialDocumentId, documents]);

  useEffect(() => {
    if (!initialDocumentId || !selectedGroupId) {
      return;
    }
    if (initialGroupId && selectedGroupId !== initialGroupId) {
      return;
    }

    setSearchQuery('');
    void loadDocuments('', selectedGroupId);
  }, [initialDocumentId, initialGroupId, selectedGroupId]);

  useEffect(() => {
    setSearchQuery('');
    setCommentText('');
    setQaQuestion('');
    setQaAnswer(null);
    setPreviewDocument(null);
    setGroupDetailOpen(false);
    setSelectedGroupDetail(null);
    setDocuments([]);
    setSelectedDocumentId(null);
    void loadDocuments('', selectedGroupId);
  }, [selectedGroupId]);

  useEffect(() => {
    if (!selectedGroupId || !documents.some((document) => document.index_status === 'indexing')) {
      return;
    }

    const refreshTimer = window.setInterval(() => {
      void loadDocuments(searchQuery, selectedGroupId, { showLoading: false });
    }, 5000);

    return () => window.clearInterval(refreshTimer);
  }, [documents, searchQuery, selectedGroupId]);

  useEffect(() => {
    let shouldIgnore = false;

    async function loadComments() {
      if (!selectedGroupId || !selectedDocumentId) {
        setComments([]);
        return;
      }

      setLoadingComments(true);
      try {
        const response = await groupApi.listComments(selectedGroupId, selectedDocumentId);
        if (!shouldIgnore) {
          setComments(response);
        }
      } catch (error) {
        if (!shouldIgnore) {
          messageApi.error(
            error instanceof Error ? error.message : 'Could not load comments.',
          );
        }
      } finally {
        if (!shouldIgnore) {
          setLoadingComments(false);
        }
      }
    }

    void loadComments();

    return () => {
      shouldIgnore = true;
    };
  }, [selectedGroupId, selectedDocumentId, messageApi]);

  useEffect(() => {
    if (!focusActivityId) {
      return;
    }

    let selector: string | null = null;

    if (mode === 'discussion') {
      if (
        !focusedCommentId ||
        loadingComments ||
        !comments.some((comment) => comment.id === focusedCommentId)
      ) {
        return;
      }
      selector = `[data-comment-id="${focusedCommentId}"]`;
    } else {
      if (
        !focusedDocumentId ||
        loadingDocuments ||
        !documents.some((document) => document.id === focusedDocumentId)
      ) {
        return;
      }
      selector = `[data-document-id="${focusedDocumentId}"]`;
    }

    const scrollTimer = window.setTimeout(() => {
      const target = shellRef.current?.querySelector<HTMLElement>(selector);
      target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
      target?.focus?.({ preventScroll: true });
    }, 80);

    return () => window.clearTimeout(scrollTimer);
  }, [
    comments,
    documents,
    focusedCommentId,
    focusedDocumentId,
    focusActivityId,
    focusRequestId,
    loadingComments,
    loadingDocuments,
    mode,
  ]);

  return (
    <section className="workspace-shell" ref={shellRef}>
      {contextHolder}
      <Modal
        centered
        className="document-preview-modal"
        footer={null}
        onCancel={() => setPreviewDocument(null)}
        open={previewDocument !== null}
        title={previewDocument?.title}
        width={860}
      >
        {previewDocument && (
          <div className="document-preview-content">
            {previewDocument.ai_summary && (
              <div className="document-preview-summary">
                <DocumentAiSummary summary={previewDocument.ai_summary} />
              </div>
            )}
            {loadingPreview ? (
              <Spin />
            ) : previewError ? (
              <div className="document-preview-fallback">
                <p>{previewError}</p>
                <Button href={previewUrl ?? undefined} target="_blank" type="primary">
                  Open file
                </Button>
              </div>
            ) : isImageDocument(previewDocument) ? (
              previewUrl ? (
                <img
                  alt={previewDocument.title}
                  className="document-preview-image"
                  src={previewUrl}
                />
              ) : (
                <Spin />
              )
            ) : isPdfDocument(previewDocument) ? (
              <>
                {previewUrl ? (
                  <iframe
                    className="document-preview-frame"
                    src={previewUrl}
                    title={previewDocument.title}
                  />
                ) : (
                  <div className="document-preview-fallback">
                    <Spin />
                  </div>
                )}
                <div className="document-preview-actions">
                  <Button href={previewUrl ?? undefined} target="_blank">
                    Open PDF in new tab
                  </Button>
                </div>
              </>
            ) : isPlainTextDocument(previewDocument) ? (
              <pre className="document-preview-text">{previewText}</pre>
            ) : isMarkdownDocument(previewDocument) ? (
              <div className="document-preview-markdown">
                {renderMarkdownBlocks(previewText ?? '')}
              </div>
            ) : (
              <div className="document-preview-fallback">
                <p>This file type cannot be previewed directly in the browser.</p>
                <Button
                  href={previewUrl ?? undefined}
                  target="_blank"
                  type="primary"
                >
                  Open file
                </Button>
              </div>
            )}
            {previewDocument.can_delete && (
              <div className="document-preview-actions">
                <Button
                  danger
                  icon={<Trash size={18} weight="bold" />}
                  onClick={() => handleDeleteDocument(previewDocument)}
                >
                  Delete
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>
      <Drawer
        className="group-detail-drawer"
        onClose={() => setGroupDetailOpen(false)}
        open={groupDetailOpen}
        title={selectedGroupDetail?.name ?? 'Group info'}
        width={460}
      >
        <Spin spinning={loadingGroupDetail}>
          {selectedGroupDetail ? (
            <div className="group-detail-content">
              <section className="group-detail-summary">
                <div>
                  <span>Course</span>
                  <strong>{formatGroupMeta(selectedGroupDetail)}</strong>
                </div>
                <div>
                  <span>Owner</span>
                  <strong>{selectedGroupDetail.owner_name}</strong>
                </div>
                <div>
                  <span>Members</span>
                  <strong>{selectedGroupDetail.member_count}</strong>
                </div>
                <div>
                  <span>Created</span>
                  <strong>{formatDate(selectedGroupDetail.created_at)}</strong>
                </div>
              </section>

              <section className="group-detail-section">
                <h3>Group properties</h3>
                <div className="group-detail-tags">
                  <Tag>{formatGroupSizeBucket(selectedGroupDetail.group_size_bucket)}</Tag>
                  <Tag>{formatPace(selectedGroupDetail.average_pace_preference)}</Tag>
                  {selectedGroupDetail.average_pace_score !== null && (
                    <Tag>Avg {selectedGroupDetail.average_pace_score}</Tag>
                  )}
                </div>
                <div className="group-detail-goals">
                  {selectedGroupDetail.top_study_goals.length === 0 ? (
                    <span>No study goals yet</span>
                  ) : (
                    selectedGroupDetail.top_study_goals.map((goal) => (
                      <Tag color="cyan" key={goal.value}>
                        {formatGoal(goal.value)} · {goal.count}
                      </Tag>
                    ))
                  )}
                </div>
              </section>

              <section className="group-detail-section">
                <h3>Members</h3>
                <div className="group-member-list">
                  {selectedGroupDetail.members.map((member) => (
                    <article className="group-member-row" key={member.user_id}>
                      <div>
                        <strong>{member.full_name}</strong>
                        <span>Joined {formatDate(member.joined_at)}</span>
                      </div>
                      <div className="group-member-tags">
                        {member.is_owner && <Tag color="gold">Owner</Tag>}
                        <Tag>{formatPace(member.pace_preference)}</Tag>
                        {member.study_goals.slice(0, 2).map((goal) => (
                          <Tag color="cyan" key={goal}>
                            {formatGoal(goal)}
                          </Tag>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          ) : (
            <Empty description="Select a group" />
          )}
        </Spin>
      </Drawer>

      <div className="workspace-header">
        <div>
          <h2>{moduleTitle}</h2>
          <p>{moduleDescription}</p>
        </div>
        <Card className="workspace-stat">
          <NotePencil size={28} weight="duotone" />
          <strong>{documents.length}</strong>
          <span>{selectedGroup ? 'shared documents' : 'select a group'}</span>
        </Card>
      </div>

      <Spin spinning={loadingGroups}>
        {groups.length === 0 ? (
          <Card className="workspace-tool-card">
            <Empty description="Create or join a group before using shared materials" />
          </Card>
        ) : (
          <div className="workspace-pane-layout">
            <Card className="workspace-switcher-card">
              <div className="tool-card-heading">
                <UsersThree size={24} weight="duotone" />
                <h2>Workspaces</h2>
              </div>
              <div className="workspace-switcher-list" aria-label="Group workspaces">
                {groups.map((group) => (
                  <button
                    aria-pressed={group.id === selectedGroupId}
                    className={
                      group.id === selectedGroupId
                        ? 'workspace-switcher-item selected'
                        : 'workspace-switcher-item'
                    }
                    key={group.id}
                    onClick={() => setSelectedGroupId(group.id)}
                    type="button"
                  >
                    <strong>{group.name}</strong>
                    <span>{formatGroupMeta(group)}</span>
                  </button>
                ))}
              </div>
            </Card>

            <div className="workspace-pane-content">
              {selectedGroup && (
                <div className="workspace-active-heading">
                  <div>
                    <span>{mode === 'workspace' ? 'Current workspace' : 'Current group'}</span>
                    <h3>{selectedGroup.name}</h3>
                    <p>{formatGroupMeta(selectedGroup)}</p>
                  </div>
                  <Button
                    icon={<Info size={18} weight="bold" />}
                    onClick={openGroupDetail}
                  >
                    Group info
                  </Button>
                </div>
              )}

              {!selectedGroup ? (
                <Card className="workspace-tool-card">
                  <Empty description="Select a group workspace" />
                </Card>
              ) : mode === 'workspace' ? (
                <div className="workspace-layout workspace-materials-layout">
                  <Card className="workspace-tool-card upload-material-card">
                    <div className="tool-card-heading">
                      <FileArrowUp size={24} weight="duotone" />
                      <h2>Upload material</h2>
                    </div>
                    <Form
                      form={uploadForm}
                      layout="vertical"
                      onFinish={handleUpload}
                      initialValues={{ document_type: 'notes' }}
                    >
                      <Form.Item
                        label="Title"
                        name="title"
                        rules={[{ required: true, message: 'Add a document title.' }]}
                      >
                        <Input placeholder="Week 5 review notes" />
                      </Form.Item>
                      <Form.Item label="Type" name="document_type">
                        <Select options={DOCUMENT_TYPES} />
                      </Form.Item>
                      <label className="workspace-file-picker">
                        <input
                          accept={SUPPORTED_UPLOAD_ACCEPT}
                          key={fileInputKey}
                          type="file"
                          onChange={handleFileChange}
                        />
                        <span>{uploadFile ? uploadFile.name : 'Choose a file'}</span>
                      </label>
                      <p style={{ fontSize: '12px', color: '#888', margin: '4px 0 0' }}>
                        Upload and preview {SUPPORTED_UPLOAD_LABEL} files, up to{' '}
                        {MAX_UPLOAD_FILE_MB} MB each.
                      </p>
                      <Button
                        block
                        htmlType="submit"
                        icon={<FileArrowUp size={18} weight="bold" />}
                        loading={uploading}
                        type="primary"
                      >
                        Upload document
                      </Button>
                    </Form>
                  </Card>

                  <Card className="workspace-tool-card document-browser">
                    <div className="tool-card-heading">
                      <MagnifyingGlass size={24} weight="duotone" />
                      <h2>Find documents</h2>
                    </div>
                    <Input.Search
                      allowClear
                      enterButton="Search"
                      onChange={(event) => setSearchQuery(event.target.value)}
                      onSearch={(value) => {
                        setSearchQuery(value);
                        void loadDocuments(value);
                      }}
                      placeholder="Search title, file name, or type"
                      value={searchQuery}
                    />

                    <Spin spinning={loadingDocuments}>
                      {documents.length === 0 ? (
                        <Empty description="No documents yet" />
                      ) : (
                        <div className="document-list">
                          {documents.map((document) => (
                            <button
                              className={classNames(
                                'document-row',
                                document.id === selectedDocumentId && 'selected',
                                mode === 'workspace' &&
                                  document.id === focusedDocumentId &&
                                  'focused-activity',
                              )}
                              data-document-id={document.id}
                              key={document.id}
                              onClick={() => {
                                setSelectedDocumentId(document.id);
                                setPreviewDocument(document);
                              }}
                              type="button"
                            >
                              <span>
                                <strong>{document.title}</strong>
                                <small>
                                  {document.file_name} uploaded by {document.uploader_name}
                                </small>
                                {document.ai_summary && (
                                  <DocumentAiSummary summary={document.ai_summary} />
                                )}
                              </span>
                              <DocumentTags document={document} />
                            </button>
                          ))}
                        </div>
                      )}
                    </Spin>
                  </Card>

                  <Card className="workspace-tool-card document-qa-card">
                    <div className="tool-card-heading">
                      <ChatCircleText size={24} weight="duotone" />
                      <h2>Ask documents</h2>
                      <span className="tool-ai-label">
                        <Sparkle size={13} weight="fill" />
                        AI
                      </span>
                    </div>
                    <div className="document-qa-composer">
                      <Input.TextArea
                        autoSize={{ minRows: 2, maxRows: 5 }}
                        onChange={(event) => setQaQuestion(event.target.value)}
                        onPressEnter={(event) => {
                          if (!event.shiftKey) {
                            event.preventDefault();
                            void handleAskDocuments();
                          }
                        }}
                        placeholder="Ask a question about this group's shared files"
                        value={qaQuestion}
                      />
                      <Button
                        disabled={!qaQuestion.trim()}
                        icon={<PaperPlaneTilt size={18} weight="bold" />}
                        loading={askingDocuments}
                        onClick={handleAskDocuments}
                        type="primary"
                      >
                        Ask
                      </Button>
                    </div>
                    {qaAnswer ? (
                      <div className="document-qa-answer">
                        <p>{qaAnswer.answer}</p>
                        {qaAnswer.sources.length > 0 && (
                          <div className="document-qa-sources">
                            {qaAnswer.sources.map((source, index) => (
                              <article
                                className="document-qa-source"
                                key={`${source.document_id ?? source.file_name}-${index}`}
                              >
                                <strong>{source.file_name}</strong>
                                <span>{source.snippet}</span>
                              </article>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <Empty description="Ask after at least one document is ready for Q&A" />
                    )}
                  </Card>
                </div>
              ) : (
                <div className="workspace-layout discussion-layout">
                  <Card className="workspace-tool-card document-browser">
                    <div className="tool-card-heading">
                      <MagnifyingGlass size={24} weight="duotone" />
                      <h2>Select document</h2>
                    </div>
                    <Input.Search
                      allowClear
                      enterButton="Search"
                      onChange={(event) => setSearchQuery(event.target.value)}
                      onSearch={(value) => {
                        setSearchQuery(value);
                        void loadDocuments(value);
                      }}
                      placeholder="Search discussion material"
                      value={searchQuery}
                    />

                    <Spin spinning={loadingDocuments}>
                      {documents.length === 0 ? (
                        <Empty description="No documents yet" />
                      ) : (
                        <div className="document-list">
                          {documents.map((document) => (
                            <button
                              className={classNames(
                                'document-row',
                                document.id === selectedDocumentId && 'selected',
                              )}
                              data-document-id={document.id}
                              key={document.id}
                              onClick={() => setSelectedDocumentId(document.id)}
                              type="button"
                            >
                              <span>
                                <strong>{document.title}</strong>
                                <small>
                                  {document.file_name} uploaded by {document.uploader_name}
                                </small>
                                {document.ai_summary && (
                                  <DocumentAiSummary summary={document.ai_summary} />
                                )}
                              </span>
                              <DocumentTags document={document} />
                            </button>
                          ))}
                        </div>
                      )}
                    </Spin>
                  </Card>

                  <Card className="workspace-detail-card">
                    {selectedDocument ? (
                      <>
                        <div className="document-detail-header">
                          <div>
                            <Tag color="green">{selectedDocument.document_type}</Tag>
                            <h2>{selectedDocument.title}</h2>
                            <p>
                              {selectedDocument.file_name} by {selectedDocument.uploader_name}
                            </p>
                          </div>
                          <div className="document-detail-actions">
                            <span>{formatDate(selectedDocument.uploaded_at)}</span>
                            <Button onClick={() => setPreviewDocument(selectedDocument)}>
                              Preview file
                            </Button>
                            {selectedDocument.can_delete && (
                              <Button
                                danger
                                icon={<Trash size={18} weight="bold" />}
                                onClick={() => handleDeleteDocument(selectedDocument)}
                              >
                                Delete
                              </Button>
                            )}
                          </div>
                        </div>

                        <div className="comment-panel">
                          <div className="tool-card-heading">
                            <ChatCircleText size={24} weight="duotone" />
                            <h3>Comments</h3>
                          </div>
                          <Spin spinning={loadingComments}>
                            {comments.length === 0 ? (
                              <Empty description="No comments yet" />
                            ) : (
                              <div className="comment-list">
                                {comments.map((comment) => (
                                  <article
                                    className={classNames(
                                      'comment-item',
                                      comment.id === focusedCommentId &&
                                        'focused-activity',
                                    )}
                                    data-comment-id={comment.id}
                                    key={comment.id}
                                    tabIndex={-1}
                                  >
                                    <div>
                                      <strong>{comment.author_name}</strong>
                                      <span>{formatDate(comment.created_at)}</span>
                                    </div>
                                    <p>{comment.content}</p>
                                  </article>
                                ))}
                              </div>
                            )}
                          </Spin>
                          <div className="comment-composer">
                            <Input.TextArea
                              autoSize={{ minRows: 3, maxRows: 5 }}
                              onChange={(event) => setCommentText(event.target.value)}
                              placeholder="Leave a note for your group"
                              value={commentText}
                            />
                            <Button
                              disabled={!commentText.trim()}
                              icon={<PaperPlaneTilt size={18} weight="bold" />}
                              loading={postingComment}
                              onClick={handlePostComment}
                              type="primary"
                            >
                              Post comment
                            </Button>
                          </div>
                        </div>
                      </>
                    ) : (
                      <Empty description="Upload or select a document to start commenting" />
                    )}
                  </Card>
                </div>
              )}
            </div>
          </div>
        )}
      </Spin>
    </section>
  );
}
