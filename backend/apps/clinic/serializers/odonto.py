from rest_framework import serializers

from apps.clinic.models.odonto import DentalProcedureContext


class DentalProcedureContextSerializer(serializers.ModelSerializer):
    scope = serializers.ChoiceField(
        choices=[
            ('tooth', 'Dente Específico'),
            ('arch', 'Arcada Inteira'),
            ('full', 'Arcada Superior e Inferior / Boca Toda'),
            ('full_arcade', 'Arcada Superior e Inferior'),
        ]
    )
    arcade_arch = serializers.ChoiceField(
        choices=[
            ('superior', 'Arcada Superior'),
            ('inferior', 'Arcada Inferior'),
            ('AMBAS', 'Arcada Superior e Inferior'),
        ],
        allow_null=True,
        required=False,
    )

    class Meta:
        model = DentalProcedureContext
        fields = ['id', 'scope', 'tooth_number', 'tooth_surface', 'arcade_arch', 'observations']

    def validate(self, attrs):
        scope = attrs.get('scope')
        arcade_arch = attrs.get('arcade_arch')

        # The combined arch is one anatomical context, never two item rows.
        if scope == 'full_arcade' or arcade_arch == 'AMBAS':
            attrs['scope'] = 'full'
            attrs['arcade_arch'] = None

        return attrs
