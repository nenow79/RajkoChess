import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from html import escape

from fastapi.concurrency import run_in_threadpool
from settings import Settings, get_settings


class EmailDeliveryError(Exception):
    pass


def build_verification_message(
    *, recipient: str, token: str, settings: Settings
) -> EmailMessage:
    verification_url = f"{settings.public_app_url}/verify-email?token={token}"
    message = EmailMessage()
    message["Subject"] = "Potwierdź adres e-mail w Rajko Chess"
    message["From"] = Address(
        settings.smtp_from_name, addr_spec=settings.smtp_from_email
    )
    message["To"] = recipient
    message.set_content(
        "Potwierdź swój adres e-mail w Rajko Chess, otwierając poniższy link:\n\n"
        f"{verification_url}\n\n"
        f"Link jest ważny przez {settings.email_verification_hours} godziny. "
        "Jeśli to nie Ty zakładałeś konto, zignoruj tę wiadomość."
    )
    safe_url = escape(verification_url, quote=True)
    message.add_alternative(
        f"""<!doctype html>
<html lang="pl"><body style="font-family:Arial,sans-serif;color:#263844">
<h1 style="font-size:24px">Potwierdź adres e-mail</h1>
<p>Dziękujemy za założenie konta w Rajko Chess.</p>
<p><a href="{safe_url}" style="display:inline-block;padding:12px 18px;background:#587d36;color:#fff;text-decoration:none;border-radius:7px">Potwierdź adres e-mail</a></p>
<p>Link jest ważny przez {settings.email_verification_hours} godziny.</p>
<p style="color:#6d7b83;font-size:13px">Jeśli to nie Ty zakładałeś konto, zignoruj tę wiadomość.</p>
</body></html>""",
        subtype="html",
    )
    return message


def build_password_reset_message(
    *, recipient: str, token: str, settings: Settings
) -> EmailMessage:
    reset_url = f"{settings.public_app_url}/reset-password?token={token}"
    message = EmailMessage()
    message["Subject"] = "Ustaw nowe hasło w Rajko Chess"
    message["From"] = Address(
        settings.smtp_from_name, addr_spec=settings.smtp_from_email
    )
    message["To"] = recipient
    message.set_content(
        "Otrzymaliśmy prośbę o ustawienie nowego hasła w Rajko Chess. "
        "Otwórz poniższy link:\n\n"
        f"{reset_url}\n\n"
        f"Link jest ważny przez {settings.password_reset_minutes} minut. "
        "Jeśli to nie Ty wysłałeś prośbę, zignoruj tę wiadomość. "
        "Twoje dotychczasowe hasło pozostanie bez zmian."
    )
    safe_url = escape(reset_url, quote=True)
    message.add_alternative(
        f"""<!doctype html>
<html lang="pl"><body style="font-family:Arial,sans-serif;color:#263844">
<h1 style="font-size:24px">Ustaw nowe hasło</h1>
<p>Otrzymaliśmy prośbę o ustawienie nowego hasła w Rajko Chess.</p>
<p><a href="{safe_url}" style="display:inline-block;padding:12px 18px;background:#587d36;color:#fff;text-decoration:none;border-radius:7px">Ustaw nowe hasło</a></p>
<p>Link jest ważny przez {settings.password_reset_minutes} minut.</p>
<p style="color:#6d7b83;font-size:13px">Jeśli to nie Ty wysłałeś prośbę, zignoruj tę wiadomość. Twoje dotychczasowe hasło pozostanie bez zmian.</p>
</body></html>""",
        subtype="html",
    )
    return message


def _send_message(message: EmailMessage, settings: Settings) -> None:
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


async def send_verification_email(*, recipient: str, token: str) -> None:
    settings = get_settings()
    try:
        settings.require_smtp()
        message = build_verification_message(
            recipient=recipient, token=token, settings=settings
        )
        await run_in_threadpool(_send_message, message, settings)
    except (OSError, RuntimeError, smtplib.SMTPException, ValueError) as exc:
        raise EmailDeliveryError from exc


async def send_password_reset_email(*, recipient: str, token: str) -> None:
    settings = get_settings()
    try:
        settings.require_smtp()
        message = build_password_reset_message(
            recipient=recipient, token=token, settings=settings
        )
        await run_in_threadpool(_send_message, message, settings)
    except (OSError, RuntimeError, smtplib.SMTPException, ValueError) as exc:
        raise EmailDeliveryError from exc
