from __future__ import annotations

from dataclasses import dataclass

from .openai_document_qa import OpenAIDocumentQA


@dataclass(frozen=True)
class AISummaryDraft:
    summary_text: str
    key_ideas: list[str]


class AIService:
    def __init__(self, document_qa: OpenAIDocumentQA | None = None) -> None:
        self.document_qa = document_qa or OpenAIDocumentQA()

    def create_study_summary(
        self,
        *,
        vector_store_id: str,
        topic: str | None = None,
        document_id: int | None = None,
    ) -> AISummaryDraft:
        focus = f" about {topic}" if topic else ""
        document_scope = (
            f" Focus only on document_id={document_id}."
            if document_id is not None
            else ""
        )
        answer = self.document_qa.answer_question(
            vector_store_id=vector_store_id,
            question=(
                f"Create a concise study summary{focus} from the shared documents."
                f"{document_scope} Format the response with a 'Summary:' section "
                "followed by a 'Key ideas:' bullet list of 3 to 5 ideas."
            ),
        )
        summary_text, key_ideas = self._parse_summary(answer.answer)
        return AISummaryDraft(summary_text=summary_text, key_ideas=key_ideas)

    def _parse_summary(self, raw_answer: str) -> tuple[str, list[str]]:
        text = " ".join(line.rstrip() for line in raw_answer.strip().splitlines())
        lines = [line.strip() for line in raw_answer.splitlines() if line.strip()]
        summary_lines: list[str] = []
        key_ideas: list[str] = []
        in_key_ideas = False

        for line in lines:
            lower_line = line.lower().rstrip(":")
            if lower_line == "summary":
                in_key_ideas = False
                continue
            if lower_line in {"key ideas", "key takeaways", "main ideas"}:
                in_key_ideas = True
                continue
            if line.lower().startswith("summary:"):
                summary_lines.append(line.split(":", 1)[1].strip())
                in_key_ideas = False
                continue
            if line.lower().startswith(("key ideas:", "key takeaways:", "main ideas:")):
                in_key_ideas = True
                remainder = line.split(":", 1)[1].strip()
                if remainder:
                    key_ideas.append(self._clean_key_idea(remainder))
                continue
            if in_key_ideas or line.startswith(("-", "*")):
                key_idea = self._clean_key_idea(line)
                if key_idea:
                    key_ideas.append(key_idea)
                continue
            summary_lines.append(line)

        summary_text = " ".join(summary_lines).strip() or text
        summary_text = " ".join(summary_text.split())
        cleaned_key_ideas = []
        for key_idea in key_ideas:
            if key_idea and key_idea not in cleaned_key_ideas:
                cleaned_key_ideas.append(key_idea)

        if not cleaned_key_ideas and summary_text:
            cleaned_key_ideas = [summary_text[:240]]
        return summary_text, cleaned_key_ideas[:5]

    def _clean_key_idea(self, value: str) -> str:
        return " ".join(value.lstrip("-*0123456789. )").split())
