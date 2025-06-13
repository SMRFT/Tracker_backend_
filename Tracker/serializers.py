from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from django.utils import timezone


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
             'columnId', 'description', 'comment',
            'startdate', 'enddate', 'members', 'created_by', 'created_date', 
            'lastmodified_by', 'lastmodified_date'
        ]
        extra_kwargs = {
            'created_by': {'read_only': True},
            'created_date': {'read_only': True},
            'lastmodified_by': {'read_only': True},
            'lastmodified_date': {'read_only': True},
        }

    def create(self, validated_data):
        # Get current employee ID from context
        current_employee_id = self.context.get('current_employee_id')
        print(f"Card Serializer create - current_employee_id: {current_employee_id}")
        
        # Set created_by directly in validated_data
        validated_data['created_by'] = current_employee_id
        validated_data['lastmodified_by'] = None
        validated_data['lastmodified_date'] = None
        
        # Create the instance
        instance = Card(**validated_data)
        instance.save()
        return instance
    
    def update(self, instance, validated_data):
        # Get current employee ID from context
        current_employee_id = self.context.get('current_employee_id')
        print(f"Card Serializer update - current_employee_id: {current_employee_id}")
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Set audit fields directly
        instance.lastmodified_by = current_employee_id
        instance.lastmodified_date = timezone.now()
        
        # Save without special parameters
        instance.save()
        return instance

class BoardSerializer(serializers.ModelSerializer):
    cards = CardSerializer(many=True, read_only=True, source='card_set')

    class Meta:
        model = Board
        fields = [
            'boardId', 'boardName', 'boardColor', 'employeeId',
            'created_by', 'created_date', 'cards', 
            'lastmodified_by', 'lastmodified_date'
        ]
        extra_kwargs = {
            'created_by': {'read_only': True},
            'created_date': {'read_only': True},
            'lastmodified_by': {'read_only': True},
            'lastmodified_date': {'read_only': True},
        }

    def create(self, validated_data):
        # Get current employee ID from context
        current_employee_id = self.context.get('current_employee_id')
        print(f"Serializer create - current_employee_id: {current_employee_id}")
        
        # Set created_by directly in validated_data
        validated_data['created_by'] = current_employee_id
        validated_data['lastmodified_by'] = None
        validated_data['lastmodified_date'] = None
        
        # Create the instance
        instance = Board(**validated_data)
        instance.save()
        return instance
    
    def update(self, instance, validated_data):
        # Get current employee ID from context
        current_employee_id = self.context.get('current_employee_id')
        print(f"Serializer update - current_employee_id: {current_employee_id}")
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Set audit fields directly
        instance.lastmodified_by = current_employee_id
        instance.lastmodified_date = timezone.now()
        
        # Save without special parameters
        instance.save()
        return instance
