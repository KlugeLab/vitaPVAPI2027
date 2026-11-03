from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    return Response({
        'servicio': 'SSucursalAPI',
        'estado': 'OK',
        'tipo_nodo': settings.VITA_TIPO_NODO,
    })
