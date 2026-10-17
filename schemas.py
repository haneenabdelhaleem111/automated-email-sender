
# from pydantic import BaseModel, EmailStr, Field, ConfigDict


# class EmailRequest(BaseModel):
#     model_config = ConfigDict(str_strip_whitespace=True)

#     recipient_email: EmailStr
#     subject: str = Field(min_length=1, max_length=200)
#     body: str = Field(min_length=1, max_length=10000)

from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class EmailRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    recipient_email: EmailStr | None = None
    recipient_emails: list[EmailStr] | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_recipients(self):
        if self.recipient_email is None and not self.recipient_emails:
            raise ValueError(
                "Provide recipient_email or recipient_emails."
            )

        if self.recipient_email is not None and self.recipient_emails:
            raise ValueError(
                "Provide either recipient_email or recipient_emails, not both."
            )

        if self.recipient_emails:
            normalized = [
                str(email).strip().casefold()
                for email in self.recipient_emails
            ]

            if len(normalized) != len(set(normalized)):
                raise ValueError(
                    "Recipient email addresses must not contain duplicates."
                )

        return self
