from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import (
    get_openai_api_key,
    get_openai_doc_qa_enabled,
    get_openai_doc_qa_model,
)


class DocumentQAError(RuntimeError):
    pass


class DocumentQAUnavailable(DocumentQAError):
    pass


@dataclass(frozen=True)
class IndexedDocument:
    openai_file_id: str
    openai_vector_store_file_id: str
    status: str


@dataclass(frozen=True)
class DocumentQASourceResult:
    document_id: int | None
    file_name: str
    snippet: str


@dataclass(frozen=True)
class DocumentQAAnswer:
    answer: str
    sources: list[DocumentQASourceResult]


def _read_attr(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _coerce_document_id(raw_value: Any) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


class OpenAIDocumentQA:
    def _client(self) -> Any:
        if not get_openai_doc_qa_enabled():
            raise DocumentQAUnavailable("OpenAI document Q&A is disabled.")

        api_key = get_openai_api_key()
        if not api_key:
            raise DocumentQAUnavailable("OPENAI_API_KEY is not configured.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise DocumentQAUnavailable("The OpenAI Python SDK is not installed.") from exc

        return OpenAI(api_key=api_key)

    def create_vector_store(self, group_id: int, group_name: str) -> str:
        vector_store = self._client().vector_stores.create(
            name=f"StudySync group {group_id}: {group_name}",
        )
        vector_store_id = _read_attr(vector_store, "id")
        if not vector_store_id:
            raise DocumentQAError("OpenAI did not return a vector store id.")
        return str(vector_store_id)

    def index_document(
        self,
        *,
        vector_store_id: str,
        file_path: Path,
        group_id: int,
        document_id: int,
        file_name: str,
    ) -> IndexedDocument:
        client = self._client()
        with file_path.open("rb") as input_file:
            uploaded_file = client.files.create(file=input_file, purpose="assistants")

        openai_file_id = str(_read_attr(uploaded_file, "id", ""))
        if not openai_file_id:
            raise DocumentQAError("OpenAI did not return an uploaded file id.")

        attributes = {
            "group_id": str(group_id),
            "document_id": str(document_id),
            "file_name": file_name,
        }
        vector_store_files = client.vector_stores.files
        if hasattr(vector_store_files, "create_and_poll"):
            vector_store_file = vector_store_files.create_and_poll(
                vector_store_id=vector_store_id,
                file_id=openai_file_id,
                attributes=attributes,
            )
        else:
            vector_store_file = vector_store_files.create(
                vector_store_id=vector_store_id,
                file_id=openai_file_id,
                attributes=attributes,
            )

        vector_store_file_id = str(_read_attr(vector_store_file, "id", ""))
        if not vector_store_file_id:
            raise DocumentQAError("OpenAI did not return a vector store file id.")

        openai_status = str(_read_attr(vector_store_file, "status", "completed"))
        index_status = "ready" if openai_status == "completed" else "indexing"
        return IndexedDocument(
            openai_file_id=openai_file_id,
            openai_vector_store_file_id=vector_store_file_id,
            status=index_status,
        )

    def answer_question(self, *, vector_store_id: str, question: str) -> DocumentQAAnswer:
        response = self._client().responses.create(
            model=get_openai_doc_qa_model(),
            instructions=(
                "You answer questions for a study group using only the documents "
                "available through file_search. If the documents do not contain the "
                "answer, say that the shared documents do not include enough "
                "information. Keep answers concise and grounded in cited evidence."
            ),
            input=question,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                    "max_num_results": 5,
                }
            ],
            include=["file_search_call.results"],
        )

        answer = str(_read_attr(response, "output_text", "")).strip()
        sources = self._extract_sources(response)
        return DocumentQAAnswer(answer=answer, sources=sources)

    def summarize_document(
        self,
        *,
        vector_store_id: str,
        document_id: int,
        file_name: str,
    ) -> str:
        response = self._client().responses.create(
            model=get_openai_doc_qa_model(),
            instructions=(
                "Write exactly one concise sentence summarizing the requested "
                "study document. Use only file_search results from the matching "
                "document_id and file name. If the document cannot be found, say "
                "that the document summary is unavailable."
            ),
            input=(
                "Summarize the study document with "
                f"document_id={document_id} and file_name={file_name!r}."
            ),
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [vector_store_id],
                    "max_num_results": 5,
                }
            ],
        )
        summary = str(_read_attr(response, "output_text", "")).strip()
        return " ".join(summary.split())

    def delete_document(
        self,
        *,
        vector_store_id: str | None,
        vector_store_file_id: str | None,
        openai_file_id: str | None,
    ) -> None:
        client = self._client()
        if vector_store_id and vector_store_file_id:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=vector_store_file_id,
            )
        if openai_file_id:
            client.files.delete(openai_file_id)

    def _extract_sources(self, response: Any) -> list[DocumentQASourceResult]:
        sources: list[DocumentQASourceResult] = []
        seen: set[tuple[int | None, str, str]] = set()

        for output_item in _read_attr(response, "output", []) or []:
            if _read_attr(output_item, "type") != "file_search_call":
                continue
            for result in _read_attr(output_item, "results", []) or []:
                attributes = _read_attr(result, "attributes", {}) or {}
                document_id = _coerce_document_id(_read_attr(attributes, "document_id"))
                file_name = (
                    _read_attr(attributes, "file_name")
                    or _read_attr(result, "filename")
                    or "Shared document"
                )
                snippet = str(_read_attr(result, "text", "")).strip()
                if not snippet:
                    continue
                key = (document_id, str(file_name), snippet)
                if key in seen:
                    continue
                seen.add(key)
                sources.append(
                    DocumentQASourceResult(
                        document_id=document_id,
                        file_name=str(file_name),
                        snippet=snippet,
                    )
                )

        return sources[:5]
