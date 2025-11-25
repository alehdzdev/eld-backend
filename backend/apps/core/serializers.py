# -*- coding: utf-8 -*-
from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    meta = serializers.DictField()


class TripPlanRequestSerializer(serializers.Serializer):
    start = serializers.CharField(help_text="Starting address or city")
    pickup = serializers.CharField(help_text="Pickup address or city")
    dropoff = serializers.CharField(help_text="Dropoff address or city")
    cycleUsed = serializers.FloatField(
        required=False, default=0.0, help_text="Hours of service cycle already used"
    )


class LogEntrySerializer(serializers.Serializer):
    status = serializers.CharField()
    startMinute = serializers.IntegerField()
    endMinute = serializers.IntegerField()
    duration = serializers.IntegerField()
    note = serializers.CharField()


class LogDaySerializer(serializers.Serializer):
    date = serializers.CharField()
    miles = serializers.FloatField()
    entries = LogEntrySerializer(many=True)


class RouteDataSerializer(serializers.Serializer):
    totalMiles = serializers.FloatField()
    locations = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField())
    )


class TripPlanResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    routeData = RouteDataSerializer()
    logs = LogDaySerializer(many=True)
