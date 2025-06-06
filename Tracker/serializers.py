from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import serializers


from bson import ObjectId
class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)
    


from .models import Board, Card

class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = [
            'cardId', 'cardName', 'boardId', 'boardName', 'employeeId',
            'employeeName', 'columnId', 
            'startdate', 'enddate', 'members', 'createdDate', 'createdTime'
        ]


class BoardSerializer(serializers.ModelSerializer):
    cards = CardSerializer(many=True, read_only=True, source='card_set')

    class Meta:
        model = Board
        fields = [
            'boardId', 'boardName', 'boardColor', 'employeeId',
            'employeeName', 'createdDate', 'createdTime', 'cards'
        ]


        
