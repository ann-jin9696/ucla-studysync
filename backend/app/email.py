from __future__ import annotations

import html
import logging
from urllib.parse import quote

import httpx

from .config import get_frontend_url, get_resend_api_key, get_resend_from_email


logger = logging.getLogger(__name__)
RESEND_EMAILS_URL = "https://api.resend.com/emails"
DASHBOARD_PATH = "/dashboard"


def branded_email(
    *,
    preheader: str,
    headline: str,
    greeting_name: str,
    paragraphs: list[str],
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_note: str | None = None,
) -> str:
    safe_preheader = html.escape(preheader)
    safe_headline = html.escape(headline)
    safe_name = html.escape(greeting_name)
    paragraph_html = "\n".join(
        f"""
        <p style="margin: 0 0 16px; color: #35554b; font-size: 16px; line-height: 1.65;">
          {html.escape(paragraph)}
        </p>
        """
        for paragraph in paragraphs
    )
    button_html = ""
    if cta_label and cta_url:
        safe_cta_label = html.escape(cta_label)
        safe_cta_url = html.escape(cta_url, quote=True)
        button_html = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 26px 0 8px;">
          <tr>
            <td style="border-radius: 14px; background: #3b9f89;">
              <a href="{safe_cta_url}" style="display: inline-block; padding: 14px 22px; color: #ffffff; font-size: 16px; font-weight: 700; text-decoration: none;">
                {safe_cta_label}
              </a>
            </td>
          </tr>
        </table>
        """

    safe_footer_note = html.escape(
        footer_note
        or "You are receiving this because you use StudySync group matching."
    )

    return f"""
    <!doctype html>
    <html>
      <body style="margin: 0; padding: 0; background: #fffaf0; font-family: Arial, Helvetica, sans-serif;">
        <div style="display: none; max-height: 0; overflow: hidden; opacity: 0;">
          {safe_preheader}
        </div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background: #fffaf0; padding: 28px 12px;">
          <tr>
            <td align="center">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 620px; overflow: hidden; border: 1px solid #dcefe7; border-radius: 24px; background: #ffffff;">
                <tr>
                  <td style="padding: 0; background: #24483e;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="padding: 28px 30px;">
                          <table role="presentation" cellspacing="0" cellpadding="0">
                            <tr>
                              <td style="width: 54px; height: 54px; border-radius: 18px; background: #f7d970; color: #24483e; font-size: 20px; font-weight: 800; text-align: center;">
                                SS
                              </td>
                              <td style="padding-left: 14px;">
                                <div style="color: #bfe8da; font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;">
                                  StudySync
                                </div>
                                <div style="color: #ffffff; font-size: 26px; font-weight: 800; line-height: 1.2;">
                                  {safe_headline}
                                </div>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                    <div style="height: 10px; background: linear-gradient(90deg, #f7d970 0%, #79cfb7 50%, #3b9f89 100%);"></div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 34px 30px 18px;">
                    <div style="margin-bottom: 20px; padding: 14px 16px; border: 1px solid #dcefe7; border-radius: 16px; background: #f4fff7; color: #277763; font-size: 13px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;">
                      UCLA study groups, organized
                    </div>
                    <p style="margin: 0 0 16px; color: #24483e; font-size: 18px; font-weight: 700;">
                      Hi {safe_name},
                    </p>
                    {paragraph_html}
                    {button_html}
                  </td>
                </tr>
                <tr>
                  <td style="padding: 0 30px 30px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-radius: 18px; background: #fff8d9;">
                      <tr>
                        <td style="padding: 18px; color: #5d6f68; font-size: 13px; line-height: 1.6;">
                          <strong style="color: #24483e;">StudySync note:</strong>
                          {safe_footer_note}
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    api_key = get_resend_api_key()
    if not api_key:
        logger.info("Skipping email because RESEND_API_KEY is not configured.")
        return False

    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                RESEND_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": get_resend_from_email(),
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
            )
            response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Resend could not deliver email to %s.", to_email)
        return False

    return True


def send_verification_email(to_email: str, full_name: str, token: str) -> bool:
    link = f"{get_frontend_url()}/verify-email?token={quote(token)}"
    return send_email(
        to_email,
        "Verify your StudySync email",
        branded_email(
            preheader="Confirm your UCLA email address to finish StudySync setup.",
            headline="Verify your email",
            greeting_name=full_name,
            paragraphs=[
                "Confirm your UCLA email address to finish setting up StudySync.",
                "After verification, you can finish your profile, match with groups, and use shared workspaces.",
            ],
            cta_label="Verify email",
            cta_url=link,
            footer_note="This verification link expires in 24 hours.",
        ),
    )


def send_password_reset_email(to_email: str, full_name: str, token: str) -> bool:
    link = f"{get_frontend_url()}/reset-password?token={quote(token)}"
    return send_email(
        to_email,
        "Reset your StudySync password",
        branded_email(
            preheader="Use this secure link to choose a new StudySync password.",
            headline="Reset your password",
            greeting_name=full_name,
            paragraphs=[
                "Use this secure link to choose a new StudySync password.",
                "If you did not request this reset, you can ignore this email and your password will stay unchanged.",
            ],
            cta_label="Reset password",
            cta_url=link,
            footer_note="This password reset link expires in 2 hours.",
        ),
    )


def send_group_application_reviewer_email(
    reviewer_email: str,
    reviewer_name: str,
    applicant_name: str,
    group_name: str,
) -> bool:
    dashboard_url = f"{get_frontend_url()}{DASHBOARD_PATH}"
    return send_email(
        reviewer_email,
        f"New StudySync application for {group_name}",
        branded_email(
            preheader=f"{applicant_name} applied to join {group_name}.",
            headline="New group application",
            greeting_name=reviewer_name,
            paragraphs=[
                f"{applicant_name} applied to join {group_name}.",
                "Open StudySync to review the application and keep your group roster moving.",
            ],
            cta_label="Review application",
            cta_url=dashboard_url,
        ),
    )


def send_group_application_decision_email(
    applicant_email: str,
    applicant_name: str,
    group_name: str,
    decision: str,
) -> bool:
    dashboard_url = f"{get_frontend_url()}{DASHBOARD_PATH}"
    return send_email(
        applicant_email,
        f"Your StudySync application was {decision}",
        branded_email(
            preheader=f"Your application to {group_name} was {decision}.",
            headline=f"Application {decision}",
            greeting_name=applicant_name,
            paragraphs=[
                f"Your application to {group_name} was {decision}.",
                "Open StudySync to see your current groups and applications.",
            ],
            cta_label="Open StudySync",
            cta_url=dashboard_url,
        ),
    )
