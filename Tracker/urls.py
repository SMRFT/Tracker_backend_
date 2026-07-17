from django.urls import path
from .Views import board, card, comment, members, notifications, security, fileshandling, deadlinecheck

urlpatterns = [
    path('change-password/', security.change_password, name='change_password'),

    path('upload-content/', fileshandling.upload_content, name='upload_content'),
    path('get-file/<str:board_id>/<str:card_id>/', fileshandling.get_file, name='get_file'),
    path('get-files/', fileshandling.get_files, name='get_files'),
    path('delete-file/<str:board_id>/<str:card_id>/<str:filename>/', fileshandling.delete_file, name='delete_file'),

    path('cards/<str:card_id>/restore/', card.restore_card, name='card-restore'),
    path('cards/<int:board_id>/<str:userRole>/', card.CardCreateView, name='card-list'),
    path('cards/<str:card_id>/<int:board_id>/<str:userRole>/', card.CardCreateView, name='card-detail'),
    path('cards/<str:card_id>/', card.CardCreateView, name='card-detail'),
    path("deleted_cards/",card.get_inactive_cards, name="get_inactive_cards"),
    path('save-description/', fileshandling.save_description, name='save_description'),

    path('employeecards/<str:employee_id>/<int:board_id>/', card.get_employee_cards, name='get_employee_cards'),

    path('boards/', board.BoardsView, name='boards-list'),
    path('boards/<int:boardId>/', board.BoardsView, name='board-detail'),
    path('get-boards/<str:role>/', board.GetBoardsView, name='boards-list'),

    path('save_comment/', comment.save_comment, name='save_comment'),
    path('get_comments/', comment.get_comments, name='get_comments'),
    path('delete_comment/', comment.delete_comment, name='delete_comment'),
    path('edit_comment/', comment.edit_comment, name='edit_comment'),
    path('download_file/<str:file_id>/', comment.download_file, name='edit_comment'),

    path('get-employees/', members.get_all_employees, name='get_all_employees'),
    path('add_member_to_card/', members.add_member_to_card, name='add_member_to_card'),
    path('employees/<int:board_id>/', members.get_board_employees, name='get_board_employees'),

    path('notifications/', notifications.get_dynamic_notifications, name='get_notifications'),
    path('notifications/mark-read/', notifications.mark_notifications_as_read),
    path('notifications/clear/', notifications.clear_notifications),
    path('notifications/clear/<str:notification_id>/', notifications.clear_single_notification),

    path("check-deadline/", deadlinecheck.check_deadline, name="check_deadline"),
    path('get-overdue-cards/<str:role>/', card.GetOverdueCardsView, name='get-overdue-cards'),

    path('cards/done/date-range/', card.get_done_cards_by_date, name='get_done_cards_by_date'),

]
