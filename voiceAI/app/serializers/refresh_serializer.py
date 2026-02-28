from rest_framework import serializers


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()
