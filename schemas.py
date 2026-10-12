
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class EmailRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recipient_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)
