# Tracker/views/deadlinecheck.py
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
import json  # Added import for json

from Tracker.models import Card
from .members import get_admin_emails
from pyauth.auth import HasRolePermission  # Adjust import if needed


def _build_overdue_email(card_details, dashboard_url=None):
    subject = "⚠️ Action Required: Overdue Tasks Detected"

    # --------- Plain text fallback ---------
    text_message = "Hello Admin,\n\nThe following tasks are overdue:\n\n"
    for card in card_details:
        members = card["members"] if isinstance(card["members"], list) else []
        text_message += (
            f"- {card['cardName']} (Card ID: {card['cardId']}, Board: {card['boardName']})\n"
            f"  Status: {card['columnId']}, End Date: {card['enddate'] or 'None'}\n"
            f"  Members: {', '.join([m['employeeName'] for m in members]) if members else 'None'}\n\n"
        )
    if dashboard_url:
        text_message += f"Open Tracker: {dashboard_url}\n"
    text_message += "\n— Tracker Notification System"

    # --------- Modern HTML UI ---------
    items_html = ""
    for card in card_details:
        members = card["members"] if isinstance(card["members"], list) else []
        members_html = ", ".join([m['employeeName'] for m in members]) if members else "None"

        # Badge color based on status
        status_colors = {
            "do": "#f59e0b",       # amber
            "doing": "#3b82f6",    # blue
            "hold": "#ef4444",     # red
            "done": "#10b981",     # green
        }
        status_color = status_colors.get(card['columnId'], "#6b7280")

        items_html += f"""
        <div style="margin-bottom:18px;padding:16px;border:1px solid #e5e7eb;
                    border-radius:12px;background:#f9fafb;box-shadow:0 1px 3px rgba(0,0,0,0.08)">
          <h3 style="margin:0 0 10px;font-size:17px;color:#111827;font-weight:600">
            {card['cardName']}
          </h3>
          <span style="display:inline-block;padding:3px 10px;font-size:12px;
                       background:{status_color};color:white;border-radius:8px;">
            {card['columnId'].capitalize()}
          </span>

          <table style="margin-top:12px;width:100%;font-size:14px;color:#374151">
            <tr><td><strong>Card ID:</strong></td><td>{card['cardId']}</td></tr>
            <tr><td><strong>Board:</strong></td><td>{card['boardName']} (ID: {card['boardId']})</td></tr>
            <tr><td><strong>Employee ID:</strong></td><td>{card['employeeId']}</td></tr>
            <tr><td><strong>Description:</strong></td><td>{card['description'] or 'None'}</td></tr>
            <tr><td><strong>Members:</strong></td><td>{members_html}</td></tr>
            <tr><td><strong>Start Date:</strong></td><td>{card['startdate'] or 'None'}</td></tr>
            <tr><td><strong>End Date:</strong></td><td>{card['enddate'] or 'None'}</td></tr>
            <tr><td><strong>Created By:</strong></td><td>{card.get('created_by', 'Unknown')}</td></tr>
            <tr><td><strong>Created Date:</strong></td><td>{card.get('created_date', 'Unknown')}</td></tr>
            <tr><td><strong>Last Modified By:</strong></td><td>{card.get('lastmodified_by', 'Unknown')}</td></tr>
            <tr><td><strong>Last Modified Date:</strong></td><td>{card.get('lastmodified_date', 'Unknown')}</td></tr>
          </table>
        </div>
        """

    # CTA button
    button_html = (
        f"""
        <a href="{dashboard_url}" target="_blank"
           style="display:inline-block;margin:20px 0;padding:14px 22px;
                  text-decoration:none;background:linear-gradient(90deg,#2563eb,#1d4ed8);
                  color:#ffffff;border-radius:12px;font-weight:600;box-shadow:0 2px 6px rgba(0,0,0,0.2)">
           🔗 Open Tracker
        </a>
        """
        if dashboard_url else ""
    )

    html_message = f"""
    <div style="font-family:Segoe UI,Roboto,Arial,sans-serif;max-width:680px;
                margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;
                border-radius:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
      <div style="background:linear-gradient(90deg,#1f2937,#111827);
                  color:#ffffff;padding:20px 24px">
        <h2 style="margin:0;font-size:20px">⚠️ Overdue Task Alert</h2>
      </div>

      <div style="padding:24px">
        <p style="margin:0 0 14px;color:#111827;font-size:15px">
          Hello Admin,
        </p>
        <p style="margin:0 0 16px;color:#374151;font-size:15px;line-height:1.5">
          The following tasks have <strong>missed their deadlines</strong> and are
          not yet marked as <b>done</b>:
        </p>

        {items_html}

        {button_html}

        <p style="margin:20px 0 0;color:#6b7280;font-size:13px;line-height:1.4">
          💡 Tip: Regularly resolving overdue tasks keeps your workflow smooth
          and avoids project delays.
        </p>
      </div>

      <div style="background:#f3f4f6;border-top:1px solid #e5e7eb;
                  padding:14px 20px;color:#6b7280;font-size:12px;text-align:center">
        — Tracker Notification System
      </div>
    </div>
    """

    return subject, text_message, html_message

@csrf_exempt
@api_view(['GET'])  # GET because manual flag comes via query param
@permission_classes([HasRolePermission])
def check_deadline(request):
    """
    Sends overdue task reminders.
    - Auto mode: Runs only if no email sent in last 24 hours
    - Manual mode: Sends immediately regardless of last sent time
    """

    is_manual = request.GET.get('manual', 'false').lower() == 'true'

    now = timezone.now()
    one_day_ago = now - timedelta(days=1)

    # Cards overdue & not done
    overdue_filter = Q(columnId__in=["do", "doing", "hold"]) & Q(enddate__lt=now)

    if not is_manual:
        overdue_filter &= (Q(last_mail_sent_date__isnull=True) | Q(last_mail_sent_date__lt=one_day_ago))

    overdue_cards = Card.objects.filter(overdue_filter).distinct()

    card_details = []

    for card in overdue_cards:
        # Build details for each overdue card
        card_details.append({
            "cardId": card.cardId,
            "cardName": card.cardName,
            "boardId": card.boardId,
            "boardName": card.boardName,
            "employeeId": card.employeeId,
            "columnId": card.columnId,
            "description": card.description,
            "startdate": card.startdate.isoformat() if card.startdate else None,
            "enddate": card.enddate.isoformat() if card.enddate else None,
            "members": json.loads(card.members) if isinstance(card.members, str) else card.members,
            "created_by": card.created_by,
            "created_date": card.created_date.isoformat() if card.created_date else None,
            "lastmodified_by": card.lastmodified_by,
            "lastmodified_date": card.lastmodified_date.isoformat() if card.lastmodified_date else None,
        })

        # Update mail timestamp
        card.last_mail_sent_date = now
        card.save(update_fields=["last_mail_sent_date"])

    sent_count = len(card_details)

    # Send email if needed
    if card_details:
        admin_emails = get_admin_emails()
        if admin_emails:
            try:
                dashboard_url = getattr(settings, "FRONTEND_TRACKER_URL", None)
                subject, text_message, html_message = _build_overdue_email(
                    card_details, dashboard_url
                )

                send_mail(
                    subject=subject,
                    message=text_message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=admin_emails,
                    fail_silently=False,
                    html_message=html_message
                )
            except Exception as e:
                print(f"Error sending admin email: {e}")

    run_type = "manual" if is_manual else "auto"
    return JsonResponse({
        "status": run_type,
        "emails_sent": sent_count,
        "cards": card_details
    }, safe=False)
