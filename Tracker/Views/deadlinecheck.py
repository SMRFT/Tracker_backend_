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
from django.core.mail import EmailMultiAlternatives

from Tracker.models import Card
from .members import get_users_for_deadline_mail
from pyauth.auth import HasRolePermission  # Adjust import if needed

# ---------------- ROLE CONSTANTS ----------------
SUPER_ADMIN_ROLES = ("ST-R-SA",)
ADMIN_ROLES = ("ST-R-A",)
HOD_ROLES = ("ST-R-HOD",)
EMP_ROLES = ("ST-R-EMP",)

ALL_ALLOWED_ROLES = SUPER_ADMIN_ROLES + ADMIN_ROLES + HOD_ROLES + EMP_ROLES


# ---------------- ROLE HELPERS ----------------
def get_user_roles(user):
    roles = []
    if user.get("primaryRole"):
        roles.append(user["primaryRole"])
    if isinstance(user.get("additionalRoles"), list):
        roles.extend(user["additionalRoles"])
    return roles

def is_user_related_to_card(card, employee_id):
    if str(card.employeeId) == str(employee_id):
        return True

    members = json.loads(card.members) if isinstance(card.members, str) else card.members
    if not members:
        return False

    return any(str(m.get("employeeId")) == str(employee_id) for m in members)

def _build_overdue_email(card_details, dashboard_url=None):
    subject = "⚠️ Action Required: Overdue Tasks Detected"

    # --------- Plain text fallback ---------
    text_message = "Hello,\n\nThe following tasks are overdue:\n\n"
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

# ---------------- MAIN API ----------------
@csrf_exempt
@api_view(["GET"])
@permission_classes([HasRolePermission])
def check_deadline(request):
    is_manual = request.GET.get("manual", "false").lower() == "true"

    now = timezone.now()
    one_day_ago = now - timedelta(days=1)

    overdue_filter = Q(columnId__in=["do", "doing", "hold"]) & Q(enddate__lt=now)

    if not is_manual:
        overdue_filter &= (
            Q(last_mail_sent_date__isnull=True)
            | Q(last_mail_sent_date__lt=one_day_ago)
        )

    overdue_cards = list(Card.objects.filter(overdue_filter).distinct())

    if not overdue_cards:
        return JsonResponse({"status": "no-overdue-cards"})

    card_details = []
    for card in overdue_cards:
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
        })

        card.last_mail_sent_date = now
        card.save(update_fields=["last_mail_sent_date"])

    users = get_users_for_deadline_mail()
    dashboard_url = getattr(settings, "FRONTEND_TRACKER_URL", None)

    role_users = {
        "SUPER_ADMIN": [],
        "ADMIN": [],
        "HOD": [],
        "EMP": [],
    }

    for user in users:
        roles = get_user_roles(user)
        if not user.get("email"):
            continue

        if any(r in SUPER_ADMIN_ROLES for r in roles):
            role_users["SUPER_ADMIN"].append(user)
        elif any(r in ADMIN_ROLES for r in roles):
            role_users["ADMIN"].append(user)
        elif any(r in HOD_ROLES for r in roles):
            role_users["HOD"].append(user)
        elif any(r in EMP_ROLES for r in roles):
            role_users["EMP"].append(user)

    role_cards = {
        "SUPER_ADMIN": card_details,
        "ADMIN": card_details,
        "HOD": [],
        "EMP": [],
    }

    for card_obj, card_data in zip(overdue_cards, card_details):
        for user in role_users["HOD"]:
            if is_user_related_to_card(card_obj, user["employeeId"]):
                role_cards["HOD"].append(card_data)

        for user in role_users["EMP"]:
            if is_user_related_to_card(card_obj, user["employeeId"]):
                role_cards["EMP"].append(card_data)

    def send_group_mail(to_users, cc_users, cards):
        if not to_users or not cards:
            return 0
        print("\n========== SENDING DEADLINE MAIL ==========")
        print("TO :", [u["email"] for u in to_users])
        print("CC :", [u["email"] for u in cc_users])
        print("Cards included :", len(cards))
        for c in cards:
            print(f"  - {c['cardId']} | {c['cardName']}")

        subject, text_msg, html_msg = _build_overdue_email(cards, dashboard_url)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_msg,
            from_email=settings.EMAIL_HOST_USER,
            to=[u["email"] for u in to_users],
            cc=[u["email"] for u in cc_users],
        )
        msg.attach_alternative(html_msg, "text/html")
        msg.send()
        return 1

    email_sent = 0

    email_sent += send_group_mail(
        role_users["SUPER_ADMIN"],
        role_users["ADMIN"],
        role_cards["SUPER_ADMIN"],
    )

    email_sent += send_group_mail(
        role_users["ADMIN"],
        role_users["HOD"],
        role_cards["ADMIN"],
    )

    email_sent += send_group_mail(
        role_users["HOD"],
        role_users["EMP"],
        role_cards["HOD"],
    )

    email_sent += send_group_mail(
        role_users["EMP"],
        [],
        role_cards["EMP"],
    )
    

    return JsonResponse({
        "status": "manual" if is_manual else "auto",
        "emails_sent": email_sent,
    })