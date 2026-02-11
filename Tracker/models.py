from django.db import models
from django.utils.timezone import now
from django.utils import timezone

class AuditModel(models.Model):
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(blank=True, null=True)
    class Meta:
        abstract = True

class Board(AuditModel):
    boardId = models.PositiveIntegerField(unique=True, blank=True, editable=False, primary_key=True)
    boardName = models.CharField(max_length=255)
    boardColor = models.CharField(max_length=250)
    employeeId = models.CharField(max_length=50)
    is_active = models.BooleanField()
    def save(self, *args, **kwargs):
        if not self.boardId:
            last_board = Board.objects.order_by('-boardId').first()
            self.boardId = (last_board.boardId + 1) if last_board and last_board.boardId else 1
        super(Board, self).save(*args, **kwargs)
    class Meta:
        db_table = 'board'
        verbose_name = 'Board'
        verbose_name_plural = 'Boards'
    def __str__(self):
        return f"{self.boardName} ({self.boardId})"

class Notification(models.Model):
    employeeId = models.CharField(max_length=50)
    cardId = models.PositiveIntegerField()
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)

    lastmodified_date = models.DateTimeField(blank=True, null=True)

class Card(AuditModel):
    boardId = models.PositiveIntegerField()
    boardName = models.CharField(max_length=255)
    employeeId = models.CharField(max_length=50)
    cardId = models.PositiveIntegerField(unique=True, blank=True, editable=False, primary_key=True)
    cardName = models.CharField(max_length=255)
    columnId = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    comment = models.JSONField(blank=True)
    startdate = models.DateField(blank=True)
    enddate = models.DateField(blank=True)
    members = models.JSONField(default=list)
    last_mail_sent_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def save(self, *args, **kwargs):
        if not self.cardId:
            last_card = Card.objects.order_by('-cardId').first()
            self.cardId = (last_card.cardId + 1) if last_card and last_card.cardId else 1
        old_card = Card.objects.filter(pk=self.pk).first()
        super(Card, self).save(*args, **kwargs)
        if old_card:
            if self.members != old_card.members:
                self.send_member_update_notification(old_card)
            if self.description != old_card.description:
                self.send_description_update_notification()
            if self.comment != old_card.comment:
                self.send_comment_update_notification()
    def send_member_update_notification(self, old_card):
        old_members = {m['employeeId'] for m in old_card.members}
        new_members = {m['employeeId'] for m in self.members}
        added_members = new_members - old_members
        for member_id in added_members:
            Notification.objects.create(
                employeeId=member_id,
                cardId=self.cardId,
                message=f"You've been added to the card '{self.cardName}'.",
            )
        for member in old_members.union(new_members):
            Notification.objects.create(
                employeeId=member,
                cardId=self.cardId,
                message=f"Members have been removed in the card '{self.cardName}'.",
            )
    def send_description_update_notification(self):
        for member in self.members:
            Notification.objects.create(
                employeeId=member['employeeId'],
                cardId=self.cardId,
                message=f"The description for the card '{self.cardName}' has been updated.",
            )
    def send_comment_update_notification(self):
        for member in self.members:
            Notification.objects.create(
                employeeId=member['employeeId'],
                cardId=self.cardId,
                message=f"A new comment has been added to the card '{self.cardName}'.",
            )
    class Meta:
        db_table = 'card'
        verbose_name = 'Card'
        verbose_name_plural = 'Cards'
    def __str__(self):
        return f"{self.cardName} ({self.cardId})"

class DeadlineEmailLog(models.Model):
    email = models.EmailField()
    role = models.CharField(max_length=30)   # SUPER_ADMIN / ADMIN / HOD / EMP
    employeeId = models.CharField(max_length=50, blank=True, null=True)

    cardIds = models.JSONField()              # [1, 5, 9]
    cardNames = models.JSONField()            # ["Task A", "Task B"]

    reason = models.JSONField()               # why email was sent
    is_manual = models.BooleanField(default=False)

    sent_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default="SENT")  # SENT / FAILED
    error = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "deadline_email_logs"

    def __str__(self):
        return f"{self.email} | {self.role} | {self.sent_at}"