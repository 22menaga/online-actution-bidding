from rest_framework import serializers
from .models import Conversation, Message, Report


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ['id', 'auction', 'buyer', 'seller', 'created_at']
        read_only_fields = ['buyer', 'seller']


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'body', 'status', 'created_at', 'read_at']
        read_only_fields = ['sender', 'status', 'read_at']


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'reporter', 'conversation', 'reason', 'details', 'status', 'reviewed_by', 'created_at', 'reviewed_at']
        read_only_fields = ['reporter', 'status', 'reviewed_by', 'reviewed_at']
