from django.urls import path
from . import views
from .Views import board, card, comment, members, notifications,security,fileshandling


urlpatterns = [
    path('register/', security.RegisterView, name='register'),
    path('change-password/', security.change_password, name='change_password'),
    path('login/', security.LoginView, name='login'),
    path('upload-content/', fileshandling.upload_content, name='upload_content'),
    path('cards/', card.CardCreateView, name='card-list'),  # For creating/listing cards
    path('cards/<str:card_id>/', card.CardCreateView, name='card-detail'),  # For retrieving/deleting specific cards by cardId
    path('cards/<str:card_id>/', card.update_card, name='update_card'),
    path('boards/', board.BoardsView, name='boards-list'),  # For GET and POST requests
    path('boards/<int:boardId>/', board.BoardsView, name='board-detail'),  # For PUT and DELETE requests
    path('get-file/<str:board_id>/<str:card_id>/', fileshandling.get_file, name='get_file'),
    path('save-description/', card.save_description, name='save_description'),
    path('get-files/', fileshandling.get_files, name='get_files'),
    path('delete-file/<str:board_id>/<str:card_id>/<str:filename>/', fileshandling.delete_file, name='delete_file'),
    path('save_comment/', comment.save_comment, name='save_comment'),
    path('get_comments/', comment.get_comments, name='get_comments'),
    path('get-boards/', board.GetBoardsView, name='boards-list'),  # For GET 
    path('boards/<int:boardId>/', board.BoardsView, name='board-detail'),  # For PUT and DELETE requests
    path('get-employees/', members.get_all_employees, name='get_all_employees'),
    path('add_member_to_card/', members.add_member_to_card, name='add_member_to_card'),
    path('notifications/', notifications.get_dynamic_notifications, name='get_notifications'),
    path('delete_comment/', comment.delete_comment, name='delete_comment'),
    path('update_card_dates/<str:card_id>/', card.update_card_dates, name='update-card-dates'),
    path('edit_comment/', comment.edit_comment, name='edit_comment'),
    path('get_board_members/<str:board_id>/', members.get_board_members, name='get_board_members'),
    path('employees/<int:board_id>/', members.get_board_employees, name='get_board_employees'),
    path('cards/<str:employee_id>/<int:board_id>/', card.get_employee_cards, name='get_employee_cards'),
    path('notifications/mark-read/', notifications.mark_notifications_as_read),

]
