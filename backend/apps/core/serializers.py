# eldplanner/serializers.py
from rest_framework import serializers


class ELDRequestSerializer(serializers.Serializer):
    ciudad_actual = serializers.CharField()
    ciudad_recogida = serializers.CharField()
    ciudad_destino = serializers.CharField()
    current_cycle_used = serializers.FloatField(min_value=0)
    api_provider = serializers.ChoiceField(
        choices=["ors", "google"], required=False, default="ors"
    )
