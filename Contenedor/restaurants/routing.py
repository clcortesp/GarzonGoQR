from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/waiter/(?P<tenant_slug>\w+)/(?P<waiter_id>\d+)/$', consumers.WaiterDashboardConsumer.as_asgi()),
] 