import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Tracker_backend.settings")
django.setup()

from Tracker.models import Card
print("Cards count:", Card.objects.count())
inactive_cards = Card.objects.filter(is_active=False)
print("Inactive cards count:", inactive_cards.count())
for card in inactive_cards[:5]:
    print(f"ID: {card.cardId}, Name: {card.cardName}, Active: {card.is_active}")
