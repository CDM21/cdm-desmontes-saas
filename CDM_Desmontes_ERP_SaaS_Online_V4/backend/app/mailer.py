import os
import smtplib
import ssl
from email.message import EmailMessage


def _env(name, default=""):
    return str(os.getenv(name, default) or "").strip()


def _smtp_sender():
    return _env("SMTP_FROM") or _env("SMTP_USER")


def smtp_diagnostics():
    host = _env("SMTP_HOST")
    sender = _smtp_sender()
    username = _env("SMTP_USER")
    password_configured = bool(os.getenv("SMTP_PASSWORD", "") or "")
    try:
        port = int(_env("SMTP_PORT", "587") or "587")
    except Exception:
        port = 587
    use_ssl = _env("SMTP_SSL", "").lower() in {"1", "true", "yes", "on"} or port == 465
    auth_ok = (not username) or password_configured
    missing = []
    if not host:
        missing.append("SMTP_HOST")
    if not sender:
        missing.append("SMTP_FROM ou SMTP_USER")
    if username and not password_configured:
        missing.append("SMTP_PASSWORD")
    return {
        "ready": bool(host and sender and auth_ok),
        "host_configured": bool(host),
        "sender_configured": bool(sender),
        "username_configured": bool(username),
        "password_configured": password_configured,
        "port": port,
        "ssl": use_ssl,
        "missing": missing,
    }


def smtp_configured():
    return bool(smtp_diagnostics()["ready"])


def send_email(to_email, subject, text_body):
    if not smtp_configured():
        return False

    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587") or "587")
    username = _env("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD", "") or ""
    sender = _smtp_sender()
    use_ssl = _env("SMTP_SSL", "").lower() in {"1", "true", "yes", "on"} or port == 465

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    return True


def send_password_reset_email(to_email, name, link):
    body = (
        f"Olá, {name or 'cliente'}.\n\n"
        "Recebemos uma solicitação para redefinir sua senha do CDM Desmontes.\n\n"
        f"Abra este link para criar uma nova senha:\n{link}\n\n"
        "O link expira em 30 minutos e deixa de funcionar depois da troca da senha.\n"
        "Se você não pediu a alteração, ignore esta mensagem."
    )
    return send_email(to_email, "Redefinição de senha - CDM Desmontes", body)
