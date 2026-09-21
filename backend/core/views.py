from datetime import timedelta

from django.db.models import Count, Exists, OuterRef
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClimateLog, Greenhouse, IrrigationCycle, PpeIssue, Zone
from .serializers import (
    ClimateLogSerializer,
    GreenhouseSerializer,
    IrrigationCycleSerializer,
    PpeIssueSerializer,
    ZoneSerializer,
)


class GreenhouseViewSet(viewsets.ModelViewSet):
    # has_open_ppe_issue 与轮灌拦截、开放核对共用 PpeIssue.open_issues() 判定
    queryset = (
        Greenhouse.objects.annotate(
            zone_count=Count("zones"),
            has_open_ppe_issue=Exists(
                PpeIssue.open_issues().filter(greenhouse=OuterRef("pk"))
            ),
        )
        .order_by("id")
        .all()
    )
    serializer_class = GreenhouseSerializer


class ZoneViewSet(viewsets.ModelViewSet):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        qs = Zone.objects.select_related("greenhouse").all()
        greenhouse_id = self.request.query_params.get("greenhouseId")
        status = self.request.query_params.get("status")
        if greenhouse_id:
            qs = qs.filter(greenhouse_id=greenhouse_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class ClimateLogViewSet(viewsets.ModelViewSet):
    serializer_class = ClimateLogSerializer

    def get_queryset(self):
        qs = ClimateLog.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        return qs


class IrrigationCycleViewSet(viewsets.ModelViewSet):
    serializer_class = IrrigationCycleSerializer

    def get_queryset(self):
        qs = IrrigationCycle.objects.select_related("zone", "zone__greenhouse").all()
        zone_id = self.request.query_params.get("zoneId")
        status = self.request.query_params.get("status")
        if zone_id:
            qs = qs.filter(zone_id=zone_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class PpeIssueViewSet(viewsets.ModelViewSet):
    serializer_class = PpeIssueSerializer

    def get_queryset(self):
        qs = PpeIssue.objects.select_related("greenhouse").all()
        greenhouse_id = self.request.query_params.get("greenhouseId")
        status = self.request.query_params.get("status")
        work_date = self.request.query_params.get("workDate")
        if greenhouse_id:
            qs = qs.filter(greenhouse_id=greenhouse_id)
        if status:
            qs = qs.filter(status=status)
        if work_date:
            qs = qs.filter(work_date=work_date)
        return qs

    @action(detail=False, methods=["get"], url_path="open-check")
    def open_check(self, request):
        # 开放核对：与温室列表 hasOpenPpeIssue、轮灌拦截共用同一判定
        open_qs = PpeIssue.open_issues()
        greenhouse_ids = list(
            open_qs.values_list("greenhouse_id", flat=True)
            .distinct()
            .order_by("greenhouse_id")
        )
        return Response(
            {
                "openIssueCount": open_qs.count(),
                "openGreenhouseCount": len(greenhouse_ids),
                "greenhouseIds": greenhouse_ids,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    data = {
        "greenhouseCount": Greenhouse.objects.count(),
        "growingZoneCount": Zone.objects.filter(status=Zone.STATUS_GROWING).count(),
        "climateLogLast24h": ClimateLog.objects.filter(
            recorded_at__gte=since_24h
        ).count(),
        "irrigationScheduledToday": IrrigationCycle.objects.filter(
            status=IrrigationCycle.STATUS_SCHEDULED,
            start_at__gte=today_start,
            start_at__lt=today_end,
        ).count(),
    }
    return Response(data)
