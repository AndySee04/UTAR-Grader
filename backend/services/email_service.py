"""Send transactional email via SMTP (e.g. Gmail)."""

from __future__ import annotations

import html
import smtplib
import ssl
from email.utils import formataddr
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib.parse import urlencode

from config import (
    FRONTEND_BASE_URL,
    SMTP_FROM,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    SMTP_USE_STARTTLS,
    smtp_configured,
)


def registration_verify_url(token: str) -> str:
    """Link opened in the app to complete email verification."""
    base = (FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    return f"{base}/verify-email?{urlencode({'token': token})}"


def grading_results_page_url(exam_id: str) -> str:
    """Direct link to exam results (same path as the app)."""
    base = (FRONTEND_BASE_URL or "http://localhost:5173").rstrip("/")
    return f"{base}/exams/{exam_id}/results"


def _greeting_name(user_name: Optional[str], to_email: str) -> str:
    if user_name and user_name.strip():
        return user_name.strip()
    if "@" in to_email:
        return to_email.split("@")[0]
    return "there"


def send_grading_complete_email(
    to_email: str,
    user_name: Optional[str],
    exam_name: str,
    exam_id: str,
    excel_bytes: bytes,
    excel_filename: str,
    zip_bytes: Optional[bytes],
    zip_filename: Optional[str],
) -> None:
    if not smtp_configured():
        return

    results_url = grading_results_page_url(exam_id)
    greeting = _greeting_name(user_name, to_email)
    safe_greeting = html.escape(greeting)
    safe_exam = html.escape(exam_name)
    safe_href = html.escape(results_url, quote=True)

    text_body = (
        f"Hi {greeting},\n\n"
        f'Grading has finished for your exam "{exam_name}".\n\n'
        f"View results:\n{results_url}\n\n"
        "Attachments on this message:\n"
        f"- {excel_filename} — class Excel summary\n"
    )
    if zip_bytes and zip_filename:
        text_body += f"- {zip_filename} — one PDF per student (ZIP)\n"
    else:
        text_body += "- (No PDF zip — no graded student summaries in this run.)\n"
    text_body += "\n— UTAR Grader\n"

    if zip_bytes and zip_filename:
        attach_pdf_li = f'<li><strong>PDFs</strong> — {html.escape(zip_filename)} (ZIP)</li>'
    else:
        attach_pdf_li = (
            "<li><strong>PDFs</strong> — not included (no graded summaries in this run).</li>"
        )

    # Table-based layout + inline styles for common mail clients (Gmail, Outlook.com, Apple Mail).
    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#eef2ff;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#eef2ff;padding:32px 16px;">
  <tr>
    <td align="center">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;width:100%;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="background-color:#4338ca;padding:24px 28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:0.18em;color:rgba(255,255,255,0.85);">UTAR GRADER</div>
            <div style="margin-top:10px;font-size:20px;font-weight:700;line-height:1.25;color:#ffffff;">Grading is complete</div>
            <div style="margin-top:6px;font-size:13px;line-height:1.45;color:rgba(255,255,255,0.88);">Your papers have been processed.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 28px 8px 28px;">
            <p style="margin:0 0 14px 0;font-size:16px;line-height:1.55;color:#0f172a;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              Hi <strong>{safe_greeting}</strong>,
            </p>
            <p style="margin:0 0 22px 0;font-size:15px;line-height:1.6;color:#475569;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              Your exam <strong style="color:#312e81;">{safe_exam}</strong> has finished grading. Use the button below to open your graded results.
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 26px 0;">
              <tr>
                <td style="border-radius:10px;background-color:#4f46e5;">
                  <a href="{safe_href}" style="display:inline-block;padding:14px 26px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
                    View graded results
                  </a>
                </td>
              </tr>
            </table>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;">
              <tr>
                <td style="padding:16px 18px;">
                  <div style="font-size:12px;font-weight:700;letter-spacing:0.06em;color:#64748b;text-transform:uppercase;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">Attachments</div>
                  <ul style="margin:10px 0 0 0;padding-left:18px;font-size:14px;line-height:1.65;color:#334155;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
                    <li><strong>Excel</strong> — {html.escape(excel_filename)}</li>
                    {attach_pdf_li}
                  </ul>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:0 28px 24px 28px;">
            <p style="margin:0;font-size:11px;line-height:1.5;color:#94a3b8;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              This message was sent automatically by UTAR Grader. If you did not run grading for this exam, you can ignore this email.
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    mailbox = SMTP_FROM or SMTP_USER
    from_header = formataddr((SMTP_FROM_NAME, mailbox))

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Grading complete: {exam_name}".replace("\n", " ").replace("\r", "")[:200]
    msg["From"] = from_header
    msg["To"] = to_email

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    xlsx = MIMEApplication(excel_bytes, _subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    xlsx.add_header("Content-Disposition", "attachment", filename=excel_filename)
    msg.attach(xlsx)

    if zip_bytes and zip_filename:
        z = MIMEApplication(zip_bytes, _subtype="zip")
        z.add_header("Content-Disposition", "attachment", filename=zip_filename)
        msg.attach(z)

    context = ssl.create_default_context()
    # SMTP envelope: must be an address Gmail accepts for this login (usually SMTP_USER).
    envelope_from = mailbox
    payload = msg.as_string()

    if SMTP_USE_STARTTLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(envelope_from, [to_email], payload)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=60) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(envelope_from, [to_email], payload)


def send_registration_verification_email(
    to_email: str,
    user_name: Optional[str],
    verify_url: str,
    expires_hours: int,
) -> None:
    """Same table-based layout as grading completion emails (UTAR Grader strip + indigo CTA)."""
    if not smtp_configured():
        return

    greeting = _greeting_name(user_name, to_email)
    safe_greeting = html.escape(greeting)
    safe_href = html.escape(verify_url, quote=True)
    safe_hours = html.escape(str(expires_hours))

    text_body = (
        f"Hi {greeting},\n\n"
        "Thanks for signing up for UTAR Grader. Confirm your email address to finish creating your account.\n\n"
        f"Open this link (or paste it into your browser):\n{verify_url}\n\n"
        f"This link expires in about {expires_hours} hours.\n\n"
        "— UTAR Grader\n"
    )

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#eef2ff;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#eef2ff;padding:32px 16px;">
  <tr>
    <td align="center">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560" style="max-width:560px;width:100%;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
        <tr>
          <td style="background-color:#4338ca;padding:24px 28px;">
            <div style="font-size:11px;font-weight:700;letter-spacing:0.18em;color:rgba(255,255,255,0.85);">UTAR GRADER</div>
            <div style="margin-top:10px;font-size:20px;font-weight:700;line-height:1.25;color:#ffffff;">Verify your email</div>
            <div style="margin-top:6px;font-size:13px;line-height:1.45;color:rgba(255,255,255,0.88);">One step left to activate your account.</div>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 28px 8px 28px;">
            <p style="margin:0 0 14px 0;font-size:16px;line-height:1.55;color:#0f172a;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              Hi <strong>{safe_greeting}</strong>,
            </p>
            <p style="margin:0 0 22px 0;font-size:15px;line-height:1.6;color:#475569;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              Confirm that this address belongs to you so we can finish setting up your UTAR Grader account.
            </p>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 26px 0;">
              <tr>
                <td style="border-radius:10px;background-color:#4f46e5;">
                  <a href="{safe_href}" style="display:inline-block;padding:14px 26px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
                    Verify email address
                  </a>
                </td>
              </tr>
            </table>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;">
              <tr>
                <td style="padding:16px 18px;">
                  <div style="font-size:12px;font-weight:700;letter-spacing:0.06em;color:#64748b;text-transform:uppercase;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">Before you go</div>
                  <ul style="margin:10px 0 0 0;padding-left:18px;font-size:14px;line-height:1.65;color:#334155;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
                    <li>This link expires in about <strong>{safe_hours} hours</strong>.</li>
                    <li>If you did not create an account, you can ignore this message.</li>
                  </ul>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:0 28px 24px 28px;">
            <p style="margin:0;font-size:11px;line-height:1.5;color:#94a3b8;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
              This message was sent automatically by UTAR Grader for email verification only.
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

    mailbox = SMTP_FROM or SMTP_USER
    from_header = formataddr((SMTP_FROM_NAME, mailbox))

    msg = MIMEMultipart("mixed")
    msg["Subject"] = "Verify your email — UTAR Grader".replace("\n", " ").replace("\r", "")[:200]
    msg["From"] = from_header
    msg["To"] = to_email

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    context = ssl.create_default_context()
    envelope_from = mailbox
    payload = msg.as_string()

    if SMTP_USE_STARTTLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(envelope_from, [to_email], payload)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=60) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(envelope_from, [to_email], payload)
