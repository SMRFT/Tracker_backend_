from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView, name='register'),
    path('change-password/', views.change_password, name='change_password'),
    path('login/', views.LoginView, name='login'),
    path('upload-content/', views.upload_content, name='upload_content'),
    path('cards/', views.CardCreateView, name='card-list'),  # For creating/listing cards
    path('cards/<str:card_id>/', views.CardCreateView, name='card-detail'),  # For retrieving/deleting specific cards by cardId
    path('cards/<str:card_id>/', views.update_card, name='update_card'),
    path('boards/', views.BoardsView, name='boards-list'),  # For GET and POST requests
    path('boards/<int:boardId>/', views.BoardsView, name='board-detail'),  # For PUT and DELETE requests
    path('get-file/<str:board_id>/<str:card_id>/', views.get_file, name='get_file'),
    path('save-description/', views.save_description, name='save_description'),
    path('get-files/', views.get_files, name='get_files'),
    path('delete-file/<str:board_id>/<str:card_id>/<str:filename>/', views.delete_file, name='delete_file'),
    path('save_comment/', views.save_comment, name='save_comment'),
    path('get_comments/', views.get_comments, name='get_comments'),
    path('get-boards/', views.GetBoardsView, name='boards-list'),  # For GET 
    path('boards/<int:boardId>/', views.BoardsView, name='board-detail'),  # For PUT and DELETE requests
    path('get-employees/', views.get_all_employees, name='get_all_employees'),
    path('add_member_to_card/', views.add_member_to_card, name='add_member_to_card'),
    path('notifications/', views.get_dynamic_notifications, name='get_notifications'),
    path('delete_comment/', views.delete_comment, name='delete_comment'),
    path('update_card_dates/<str:card_id>/', views.update_card_dates, name='update-card-dates'),
    path('edit_comment/', views.edit_comment, name='edit_comment'),
    path('get_board_members/<str:board_id>/', views.get_board_members, name='get_board_members'),
    path('employees/<int:board_id>/', views.get_board_employees, name='get_board_employees'),
    path('cards/<str:employee_id>/<int:board_id>/', views.get_employee_cards, name='get_employee_cards'),
    path('notifications/mark-read/', views.mark_notifications_as_read),

    

  
]
