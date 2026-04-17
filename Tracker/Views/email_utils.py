from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging
import json

logger = logging.getLogger(__name__)

def get_card_notification_template(employee_name, card_name, board_name, end_date, action_type):
    """
    Returns the HTML email template for card notifications.
    """
    frontend_url = getattr(settings, "FRONTEND_TRACKER_URL",'https://shinova.in/tracker')
    
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #f6676e; color: white; padding: 20px; text-align: center;">
            <h2 style="margin: 0;">Task Notification</h2>
        </div>
        <div style="padding: 20px; line-height: 1.6; color: #333;">
            <p>Hello <strong>{employee_name}</strong>,</p>
            <p>You have been {action_type} to the following task in <strong>Tracker</strong>:</p>
            <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #f6676e; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Card Name:</strong> {card_name}</p>
                <p style="margin: 5px 0;"><strong>Board:</strong> {board_name}</p>
                <p style="margin: 5px 0;"><strong>Due Date:</strong> {end_date if end_date else 'Not set'}</p>
            </div>
            <p>Please log in to the Tracker dashboard to view more details and start working on the task.</p>
            <div style="text-align: center; margin-top: 30px;">
                <a href="{frontend_url}" style="background-color: #f6676e; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Go to Dashboard</a>
            </div>
        </div>
        <div style="background-color: #f1f1f1; color: #777; padding: 10px; text-align: center; font-size: 12px;">
            This is an automated message from Tracker. Please do not reply.
        </div>
    </div>
    """

def send_card_notification_email(card, members_to_notify, profiles_collection, action_type="created"):
    """
    card: Card instance
    members_to_notify: list of member dicts
    profiles_collection: MongoDB collection for profiles
    action_type: "created" or "added"
    """
    if not members_to_notify:
        return

    subject = f"New Task Assigned: {card.cardName}" if action_type == "created" else f"You were added to Task: {card.cardName}"
    
    emp_ids = [str(m.get('employeeId')) for m in members_to_notify if m.get('employeeId')]
    if not emp_ids:
        return

    query = {
        "employeeId": {"$in": emp_ids},
        "email": {"$exists": True, "$ne": ""}
    }
    
    recipient_profiles = list(profiles_collection.find(query, {"email": 1, "employeeId": 1, "employeeName": 1, "is_active": 1}))
    print(f"🔍 [Email Utils] Searching profiles for {emp_ids}...")
    print(f"👥 [Email Utils] Found {len(recipient_profiles)} eligible profiles")

    for profile in recipient_profiles:
        if profile.get('is_active') == False:
            continue
            
        recipient_email = profile.get('email')
        emp_name = profile.get('employeeName', 'Team Member')
        
        html_content = get_card_notification_template(
            emp_name, 
            card.cardName, 
            card.boardName, 
            card.enddate, 
            action_type
        )
        
        try:
            print(f"📧 Attempting to send email to {recipient_email}...")
            msg = EmailMultiAlternatives(
                subject=subject,
                body=f"You have been {action_type} to task: {card.cardName}",
                from_email=settings.EMAIL_HOST_USER,
                to=[recipient_email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            print(f"✅ Email sent successfully to {recipient_email}")
        except Exception as e:
            print(f"❌ Failed to send email to {recipient_email}: {str(e)}")
            logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
