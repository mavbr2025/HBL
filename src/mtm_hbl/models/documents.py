from pydantic import BaseModel, Field


class PageText(BaseModel):
    page_number: int
    text: str
    confidence: float | None = None
    extraction_method: str = "embedded_text"


class LoadedDocument(BaseModel):
    path: str
    document_type: str = "unknown"
    pages: list[PageText] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)
