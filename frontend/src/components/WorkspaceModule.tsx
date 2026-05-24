import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
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

function isImageDocument(document: GroupDocument) {
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)$/i.test(document.file_name);
}

function isPdfDocument(document: GroupDocument) {
  return /\.pdf$/i.test(document.file_name);
}

function classNames(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(' ');
}

function getActivityTargetId(activityId: string | null | undefined, prefix: string) {
  const match = activityId?.match(new RegExp(`^${prefix}-(\\d+)$`));
  return match ? Number(match[1]) : null;
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
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [loadingComments, setLoadingComments] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [postingComment, setPostingComment] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<GroupDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [groupDetailOpen, setGroupDetailOpen] = useState(false);
  const [selectedGroupDetail, setSelectedGroupDetail] = useState<GroupDetail | null>(null);
  const [loadingGroupDetail, setLoadingGroupDetail] = useState(false);

  useEffect(() => {
    if (!previewDocument) {
      setPreviewUrl(null);
      return;
    }
    let objectUrl: string;
    fetch(groupApi.documentFileUrl(previewDocument.group_id, previewDocument.id), {
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Failed to load file: ${r.status}`);
        return r.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch((err) => console.error('File preview failed:', err));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
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

  async function loadDocuments(nextSearch = searchQuery, groupId = selectedGroupId) {
    if (!groupId) {
      setDocuments([]);
      setSelectedDocumentId(null);
      return;
    }

    setLoadingDocuments(true);
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
      setLoadingDocuments(false);
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
      messageApi.success('Document uploaded.');
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

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setUploadFile(event.target.files?.[0] ?? null);
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
    setPreviewDocument(null);
    setGroupDetailOpen(false);
    setSelectedGroupDetail(null);
    setDocuments([]);
    setSelectedDocumentId(null);
    void loadDocuments('', selectedGroupId);
  }, [selectedGroupId]);

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
        {previewDocument &&
          (isImageDocument(previewDocument) ? (
            <img
              alt={previewDocument.title}
              className="document-preview-image"
              src={previewUrl ?? undefined}
            />
          ) : isPdfDocument(previewDocument) ? (
            <iframe
              className="document-preview-frame"
              src={previewUrl ?? undefined}
              title={previewDocument.title}
            />
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
          ))}
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
                  <Card className="workspace-tool-card">
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
                        <input key={fileInputKey} type="file" onChange={handleFileChange} />
                        <span>{uploadFile ? uploadFile.name : 'Choose a file'}</span>
                      </label>
                      <p style={{ fontSize: '12px', color: '#888', margin: '4px 0 0' }}>
                        Only PDF and image files can be previewed in the browser.
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
                              </span>
                              <Tag color="green">{document.document_type}</Tag>
                            </button>
                          ))}
                        </div>
                      )}
                    </Spin>
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
                              </span>
                              <Tag color="green">{document.document_type}</Tag>
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
