from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session

from core.config import (
    EMAIL_PASSWORD,
    EMAIL_ID,
    EMAIL_PORT,
    EMAIL_SERVICE,
    EMAIL_FROM_NAME,
) 
from models import User, Email
from datetime import datetime
from pathlib import Path


conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL_ID,
    MAIL_PASSWORD=EMAIL_PASSWORD,
    MAIL_FROM=EMAIL_ID,
    MAIL_PORT=EMAIL_PORT,
    MAIL_SERVER=EMAIL_SERVICE,
    MAIL_FROM_NAME=EMAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates/email",
)


async def send_email(
        session: AsyncSession,
        request: Request, 
        user: User, 
        header_msg: str, 
        body_msg: str,
        recipient_email: str | None = None,  # ✅ Add direct email
        recipient_name: str | None = None,   # ✅ Add direct name
        ): 
    email = recipient_email if recipient_email else (user.email if user else None)
    name = recipient_name if recipient_name else (user.name if user else "User")
    
    if not email:
        raise ValueError("Either user or recipient_email must be provided")
    # Render the HTML body from the template to store it in the database
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(conf.TEMPLATE_FOLDER))
    template = env.get_template("user_email.html")

    template_body = {
        "username": name,
        "body": body_msg,
        "company_name": "Eisaku", 
        "current_year": datetime.now().year,
    }

    html_body = template.render(template_body)

    # Create an email log entry
    email_log = Email(
        subject=header_msg,
        body=body_msg,
        recipient_email= email,
        status="pending",
        created_by=request.state.user.id,
    )
    
    session.add(email_log)
    await session.commit()
    await session.refresh(email_log)

    message = MessageSchema(
        subject=header_msg,
        recipients=[email],
        body=html_body,
        subtype="html",
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        email_log.status = "sent"
    except Exception as e:
        email_log.status = "failed"
    
    session.add(email_log)
    await session.commit()

# async def send_onboarding_email(session: Session,request: Request,user: User):


