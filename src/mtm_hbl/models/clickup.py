from pydantic import BaseModel, Field


class ClickUpCustomField(BaseModel):
    id: str = ""
    name: str = ""
    value: object | None = None


class ClickUpAttachment(BaseModel):
    id: str = ""
    title: str = ""
    url: str = ""
    extension: str = ""


class ClickUpTaskData(BaseModel):
    id: str
    name: str = ""
    status: str = ""
    description: str = ""
    custom_fields: list[ClickUpCustomField] = Field(default_factory=list)
    attachments: list[ClickUpAttachment] = Field(default_factory=list)

    def field_by_id(self, field_id: str) -> ClickUpCustomField | None:
        return next((field for field in self.custom_fields if field.id == field_id), None)

    def field_by_name(self, field_name: str) -> ClickUpCustomField | None:
        normalized = field_name.casefold()
        return next(
            (field for field in self.custom_fields if field.name.casefold() == normalized),
            None,
        )
