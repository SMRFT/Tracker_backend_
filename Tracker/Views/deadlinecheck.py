# Tracker/views/deadlinecheck.py
from django.utils import timezone
from datetime import timedelta, datetime, date
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from django.views.decorators.csrf import csrf_exempt
import json  # Added import for json
from django.core.mail import EmailMultiAlternatives

from Tracker.models import Card,Board,DeadlineEmailLog
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


def normalize_date(value):
    """Convert date/datetime to aware datetime"""
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    if isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
        return timezone.make_aware(dt)
    return None


def is_board_owned_by_hod(board_id, hod_employee_id):
    """
    Returns True if the given HOD is the owner / in-charge of the board
    """
    return Board.objects.filter(
        boardId=board_id,
        employeeId=hod_employee_id,
        is_active=True
    ).exists()


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

    print("\n========== CHECK DEADLINE START ==========")

    is_manual = request.GET.get("manual", "false").lower() == "true"
    now = timezone.now()
    one_day_ago = now - timedelta(days=1)

    print("Manual:", is_manual)
    print("Now:", now)

    # --------------------------------------------------
    # LOAD BOARD OWNERS (Mongo safe)
    # --------------------------------------------------
    board_owner_map = {
        b.boardId: b.employeeId
        for b in Board.objects.all()
    }
    print("Board owner map:", board_owner_map)

    overdue_cards = []
    card_details = []

    # --------------------------------------------------
    # OVERDUE CARD SCAN (NO SQL)
    # --------------------------------------------------
    for card in Card.objects.all():

        print(f"\nChecking Card {card.cardId} | {card.cardName}")

        if card.columnId not in ["do", "doing", "hold"]:
            # print("  ❌ Wrong column")
            continue

        if not card.enddate:
            # print("  ❌ No enddate")
            continue

        end_dt = (
            timezone.make_aware(
                datetime.combine(card.enddate, datetime.min.time())
            )
            if isinstance(card.enddate, date) and not isinstance(card.enddate, datetime)
            else card.enddate
        )

        if end_dt >= now:
            # print("  ❌ Not overdue")
            continue

        if not is_manual and card.last_mail_sent_date:
            last_sent = card.last_mail_sent_date
            if last_sent >= one_day_ago:
                # print("  ❌ Mail sent <24h")
                continue

        # print("  ✅ OVERDUE")

        overdue_cards.append(card)

        members = json.loads(card.members) if isinstance(card.members, str) else card.members or []

        card_details.append({
            "cardId": card.cardId,
            "cardName": card.cardName,
            "boardId": card.boardId,
            "boardName": card.boardName,
            "employeeId": card.employeeId,
            "columnId": card.columnId,
            "description": card.description,
            "startdate": card.startdate,
            "enddate": card.enddate,
            "members": members,
        })

        card.last_mail_sent_date = now
        card.save(update_fields=["last_mail_sent_date"])

    print("\nTotal overdue cards:", len(overdue_cards))

    if not overdue_cards:
        return JsonResponse({"status": "no-overdue-cards"})

    # --------------------------------------------------
    # LOAD USERS
    # --------------------------------------------------
    users = get_users_for_deadline_mail()

    super_admins, admins, hods, emps = [], [], [], []

    for u in users:
        if not u.get("email"):
            continue

        roles = get_user_roles(u)

        if any(r in SUPER_ADMIN_ROLES for r in roles):
            super_admins.append(u)
        elif any(r in ADMIN_ROLES for r in roles):
            admins.append(u)
        elif any(r in HOD_ROLES for r in roles):
            hods.append(u)
        elif any(r in EMP_ROLES for r in roles):
            emps.append(u)

    # --------------------------------------------------
    # RELATION CHECKERS
    # --------------------------------------------------
    def emp_related(card, emp_id):
        member_ids = [m.get("employeeId") for m in (card.members or []) if isinstance(m, dict)]
        return card.employeeId == emp_id or emp_id in member_ids

    def hod_related(card, hod):
        member_ids = [m.get("employeeId") for m in (card.members or []) if isinstance(m, dict)]
        return (
            card.employeeId == hod["employeeId"]
            or hod["employeeId"] in member_ids
            or board_owner_map.get(card.boardId) == hod["employeeId"]
        )

    # --------------------------------------------------
    # ASSIGN CARDS
    # --------------------------------------------------
    emp_cards = {}
    hod_cards = {}

    for emp in emps:
        emp_cards[emp["email"]] = [
            d for c, d in zip(overdue_cards, card_details)
            if emp_related(c, emp["employeeId"])
        ]

    for hod in hods:
        hod_cards[hod["email"]] = [
            d for c, d in zip(overdue_cards, card_details)
            if hod_related(c, hod)
        ]

    # --------------------------------------------------
    # SAVE EMAIL LOG
    # --------------------------------------------------
    def save_log(email, role, emp_id, cards, reason, status="SENT", error=None):
        DeadlineEmailLog.objects.create(
            email=email,
            role=role,
            employeeId=emp_id,
            cardIds=[c["cardId"] for c in cards],
            cardNames=[c["cardName"] for c in cards],
            reason=reason,
            is_manual=is_manual,
            status=status,
            error=error,
        )

    dashboard_url = getattr(settings, "FRONTEND_TRACKER_URL", None)
    sent = 0

    def send_to_user(user, cards, role, reason):
        nonlocal sent
        if not cards:
            return

        try:
            print(f"\n📧 Sending {role} mail to {user['email']}")

            subject, text, html = _build_overdue_email(cards, dashboard_url)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text,
                from_email=settings.EMAIL_HOST_USER,
                to=[user["email"]],
            )
            msg.attach_alternative(html, "text/html")
            msg.send()

            save_log(
                user["email"],
                role,
                user.get("employeeId"),
                cards,
                reason,
            )

            sent += 1
            print("✅ Sent & logged")

        except Exception as e:
            save_log(
                user["email"],
                role,
                user.get("employeeId"),
                cards,
                reason,
                status="FAILED",
                error=str(e),
            )
            print("❌ Failed:", e)

    # --------------------------------------------------
    # SEND MAILS (STRICT RULES)
    # --------------------------------------------------
    for u in super_admins:
        send_to_user(u, card_details, "SUPER_ADMIN", {
            "rule": "ALL_OVERDUE",
            "desc": "Super admin receives all overdue cards"
        })

    for u in admins:
        send_to_user(u, card_details, "ADMIN", {
            "rule": "ALL_OVERDUE",
            "desc": "Admin receives all overdue cards"
        })

    for hod in hods:
        send_to_user(hod, hod_cards.get(hod["email"], []), "HOD", {
            "rule": "HOD_RELATED",
            "desc": "Board owner / member / card owner"
        })

    for emp in emps:
        send_to_user(emp, emp_cards.get(emp["email"], []), "EMP", {
            "rule": "EMP_RELATED",
            "desc": "Card owner or member"
        })

    print("\n========== CHECK DEADLINE END ==========")

    return JsonResponse({
        "status": "manual" if is_manual else "auto",
        "emails_sent": sent,
    })
