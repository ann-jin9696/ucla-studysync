import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import { Button, Card, Empty, Form, Input, Modal, Select, Spin, Tag, message } from 'antd';
import {
  ChatCircleText,
  FileArrowUp,
  MagnifyingGlass,
  NotePencil,
  PaperPlaneTilt,
} from '@phosphor-icons/react';
import type { WorkspaceDocument } from '../api';
import { workspaceApi } from '../api';

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

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

function isImageDocument(document: WorkspaceDocument) {
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)$/i.test(document.file_name);
}

function isPdfDocument(document: WorkspaceDocument) {
  return /\.pdf$/i.test(document.file_name);
}

export function WorkspaceModule({ mode }: { mode: WorkspaceModuleMode }) {
  const [messageApi, contextHolder] = message.useMessage();
  const [uploadForm] = Form.useForm<UploadFormValues>();
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null);
  const [comments, setComments] = useState<
    Awaited<ReturnType<typeof workspaceApi.listComments>>
  >([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [commentText, setCommentText] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loadingDocuments, setLoadingDocuments] = useState(true);
  const [loadingComments, setLoadingComments] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [postingComment, setPostingComment] = useState(false);
  const [previewDocument, setPreviewDocument] = useState<WorkspaceDocument | null>(null);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  async function loadDocuments(nextSearch = searchQuery) {
    setLoadingDocuments(true);
    try {
      const response = await workspaceApi.listDocuments(nextSearch);
      setDocuments(response.documents);
      setSelectedDocumentId((currentId) => {
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

  async function handleUpload(values: UploadFormValues) {
    if (!uploadFile) {
      messageApi.warning('Choose a file to upload.');
      return;
    }

    setUploading(true);
    try {
      const uploaded = await workspaceApi.uploadDocument({
        title: values.title,
        document_type: values.document_type,
        file: uploadFile,
      });
      messageApi.success('Document uploaded.');
      uploadForm.resetFields();
      setUploadFile(null);
      setFileInputKey((key) => key + 1);
      await loadDocuments(searchQuery);
      setSelectedDocumentId(uploaded.id);
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : 'Could not upload document.');
    } finally {
      setUploading(false);
    }
  }

  async function handlePostComment() {
    if (!selectedDocument || !commentText.trim()) {
      return;
    }

    setPostingComment(true);
    try {
      const created = await workspaceApi.createComment(selectedDocument.id, commentText);
      setComments((currentComments) => [...currentComments, created]);
      setCommentText('');
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
    void loadDocuments('');
  }, []);

  useEffect(() => {
    let shouldIgnore = false;

    async function loadComments() {
      if (!selectedDocumentId) {
        setComments([]);
        return;
      }

      setLoadingComments(true);
      try {
        const response = await workspaceApi.listComments(selectedDocumentId);
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
  }, [selectedDocumentId, messageApi]);

  return (
    <section className="workspace-shell">
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
              src={workspaceApi.documentFileUrl(previewDocument.id)}
            />
          ) : isPdfDocument(previewDocument) ? (
            <iframe
              className="document-preview-frame"
              src={workspaceApi.documentFileUrl(previewDocument.id)}
              title={previewDocument.title}
            />
          ) : (
            <div className="document-preview-fallback">
              <p>This file type cannot be previewed directly in the browser.</p>
              <Button
                href={workspaceApi.documentFileUrl(previewDocument.id)}
                target="_blank"
                type="primary"
              >
                Open file
              </Button>
            </div>
          ))}
      </Modal>

      <div className="workspace-header">
        <div>
          <h2>{mode === 'workspace' ? 'Shared materials' : 'Group discussion'}</h2>
          {mode === 'workspace' ? (
            <p>Upload study files and search the materials your group has shared.</p>
          ) : (
            <p>Select an uploaded document and keep group comments beside that material.</p>
          )}
        </div>
        <Card className="workspace-stat">
          <NotePencil size={28} weight="duotone" />
          <strong>{documents.length}</strong>
          <span>shared documents</span>
        </Card>
      </div>

      {mode === 'workspace' ? (
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
                      className={
                        document.id === selectedDocumentId
                          ? 'document-row selected'
                          : 'document-row'
                      }
                      key={document.id}
                      onClick={() => setPreviewDocument(document)}
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
                      className={
                        document.id === selectedDocumentId
                          ? 'document-row selected'
                          : 'document-row'
                      }
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
                          <article className="comment-item" key={comment.id}>
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
    </section>
  );
}
