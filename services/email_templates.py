"""Branded HTML email bodies. Plain functions, no template engine yet.

Every template stays short, states one thing, and links back to the app.
"""

from config.settings import settings

BRAND_LINE = "Bevis — Don't say it. Show proof."


def _shell(title: str, body: str) -> str:
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#16181d;">
<h2 style="margin:0 0 12px;">{title}</h2>
{body}
<p style="color:#6b7280;font-size:13px;margin-top:24px;">{BRAND_LINE}</p>
</div>"""


def welcome_html() -> tuple[str, str]:
    return (
        "Welcome to Bevis",
        _shell(
            "Welcome to Bevis",
            "<p>Your account is ready. Connect a repository, push something "
            "real, and your first draft will be waiting.</p>",
        ),
    )


def reset_html(reset_url: str) -> tuple[str, str]:
    return (
        "Reset your Bevis password",
        _shell(
            "Reset your Bevis password",
            f"<p>Someone asked to reset this account's password. If that was "
            f"you, use this link within the hour:</p>"
            f'<p><a href="{reset_url}">Reset password</a></p>'
            f"<p>If it wasn't you, ignore this email. Nothing changes.</p>",
        ),
    )


def post_ready_html(project_name: str, excerpt: str) -> tuple[str, str]:
    return (
        f"New draft ready for {project_name}",
        _shell(
            f"New draft ready for {project_name}",
            f"<p>Your latest push became a draft post:</p>"
            f"<blockquote>{excerpt}</blockquote>"
            f'<p><a href="{settings.frontend_url}">Review it in Bevis</a></p>',
        ),
    )


def verification_code_html(code: str) -> tuple[str, str]:
    return (
        "Your Bevis verification code",
        _shell(
            "Your Bevis verification code",
            f"<p>Enter this code to verify your email. It expires in "
            f"10 minutes:</p>"
            f'<p style="font-size:28px;letter-spacing:6px;"><b>{code}</b></p>'
            f"<p>If you didn't ask for this, ignore the email.</p>",
        ),
    )


def deletion_code_html(code: str) -> tuple[str, str]:
    return (
        "Confirm deleting your Bevis account",
        _shell(
            "Confirm deleting your Bevis account",
            f"<p>Someone asked to delete this account, including every "
            f"project and post. If that was you, enter this code within "
            f"10 minutes:</p>"
            f'<p style="font-size:28px;letter-spacing:6px;"><b>{code}</b></p>'
            f"<p>If it wasn't you, ignore the email and change your "
            f"password. Nothing is deleted without this code.</p>",
        ),
    )
