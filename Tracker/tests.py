from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.test import APIRequestFactory

from Tracker.models import Board, Card, Notification
from Tracker.serializers import BoardSerializer, CardSerializer
from Tracker.utils.employees import get_employee_name_by_id
from Tracker.utils.auth import get_auth_user_id, get_user_role
from Tracker.utils.dates import normalize_date, parse_date_range
from Tracker.utils.exception_handler import custom_api_exception_handler


class SharedUtilitiesTestCase(TestCase):
    """
    Unit tests for shared utility modules (dates, auth parsing).
    """

    def test_normalize_naive_datetime(self):
        naive_dt = timezone.datetime(2026, 7, 11, 12, 0, 0)
        self.assertTrue(timezone.is_naive(naive_dt))
        
        aware_dt = normalize_date(naive_dt)
        self.assertTrue(timezone.is_aware(aware_dt))
        self.assertFalse(timezone.is_naive(aware_dt))

    def test_parse_date_range(self):
        start_str = "2026-07-11"
        end_str = "2026-07-15"
        
        from_dt, to_dt = parse_date_range(start_str, end_str)
        
        self.assertEqual(from_dt.hour, 0)
        self.assertEqual(from_dt.minute, 0)
        self.assertEqual(to_dt.hour, 23)
        self.assertEqual(to_dt.minute, 59)


class SerializerTestCase(TestCase):
    """
    Tests checking serialization boundaries, audit-field mutations, and constraints.
    """

    def setUp(self):
        self.board = Board.objects.create(
            boardName="Test Board",
            boardColor="#FFF",
            employeeId="emp_123",
            is_active=True
        )

    def test_card_serializer_create(self):
        payload = {
            "cardName": "Sprint Planning",
            "boardId": self.board.boardId,
            "boardName": self.board.boardName,
            "employeeId": "emp_123",
            "columnId": "todo",
            "description": "Team sync",
            "startdate": "2026-07-11",
            "enddate": "2026-07-12",
            "members": [],
            "comment": []
        }
        
        context = {"current_employee_id": "creator_emp"}
        serializer = CardSerializer(data=payload, context=context)
        
        self.assertTrue(serializer.is_valid(), serializer.errors)
        card = serializer.save()
        
        # Verify custom create hooks audit-logging
        self.assertEqual(card.created_by, "creator_emp")
        self.assertIsNone(card.lastmodified_by)
        self.assertTrue(card.is_active)

    def test_card_serializer_update(self):
        card = Card.objects.create(
            boardId=self.board.boardId,
            boardName=self.board.boardName,
            employeeId="emp_123",
            cardName="Existing Task",
            columnId="todo",
            description="",
            comment=[],
            startdate="2026-07-11",
            enddate="2026-07-12",
            members=[],
            created_by="initial_creator",
            is_active=True
        )
        
        payload = {"cardName": "Renamed Task", "columnId": "doing"}
        context = {"current_employee_id": "updater_emp"}
        
        serializer = CardSerializer(card, data=payload, partial=True, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_card = serializer.save()
        
        # Verify update hooks and audit trails
        self.assertEqual(updated_card.cardName, "Renamed Task")
        self.assertEqual(updated_card.lastmodified_by, "updater_emp")
        self.assertIsNotNone(updated_card.lastmodified_date)


class CentralizedExceptionHandlerTestCase(TestCase):
    """
    Validates that exceptions map correctly to standard JSON envelopes.
    """

    def test_validation_error_mapping(self):
        exc = ValidationError(detail={"boardName": ["This field is required."]})
        context = {"view": object()}
        
        response = custom_api_exception_handler(exc, context)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "VALIDATION_FAILED")
        self.assertIn("boardName", response.data["error"]["details"])

    def test_unhandled_exception_mapping(self):
        exc = Exception("Connection lost to database backend")
        context = {"view": object()}
        
        response = custom_api_exception_handler(exc, context)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error"]["code"], "INTERNAL_SERVER_ERROR")
        # Mask original exception detail to prevent details leakage
        self.assertNotIn("Connection lost", response.data["error"]["message"])


from Tracker.Views.card import get_active_cards

class CardViewsTestCase(TestCase):
    """
    Tests for card views and active card queries.
    """

    def setUp(self):
        self.board = Board.objects.create(
            boardId=999,
            boardName="Query Board",
            boardColor="#FFF",
            employeeId="emp_123",
            is_active=True
        )
        self.card = Card.objects.create(
            boardId=999,
            boardName="Query Board",
            employeeId="emp_123",
            cardName="Active Task",
            columnId="todo",
            is_active=True
        )
        self.inactive_card = Card.objects.create(
            boardId=999,
            boardName="Query Board",
            employeeId="emp_123",
            cardName="Inactive Task",
            columnId="todo",
            is_active=False
        )

    def test_get_active_cards_helper(self):
        active_cards = get_active_cards(999)
        self.assertEqual(len(active_cards), 1)
        self.assertEqual(active_cards[0].cardName, "Active Task")

