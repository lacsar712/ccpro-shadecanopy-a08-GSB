from rest_framework import serializers

from .models import ClimateLog, Greenhouse, IrrigationCycle, PpeIssue, Zone
from .rules import greenhouse_has_open_ppe_issue, open_ppe_issues


class GreenhouseSerializer(serializers.ModelSerializer):
    areaM2 = serializers.DecimalField(
        source="area_m2", max_digits=10, decimal_places=2
    )
    zoneCount = serializers.SerializerMethodField()
    hasOpenPpeIssue = serializers.SerializerMethodField()

    class Meta:
        model = Greenhouse
        fields = (
            "id",
            "name",
            "location",
            "areaM2",
            "notes",
            "zoneCount",
            "hasOpenPpeIssue",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "zoneCount",
            "hasOpenPpeIssue",
            "created_at",
            "updated_at",
        )

    def get_zoneCount(self, obj):
        if hasattr(obj, "zone_count"):
            return obj.zone_count
        return obj.zones.count()

    def get_hasOpenPpeIssue(self, obj):
        annotated = getattr(obj, "has_open_ppe_issue", None)
        if annotated is not None:
            return bool(annotated)
        return greenhouse_has_open_ppe_issue(obj.pk)


class ZoneSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    zoneCode = serializers.CharField(source="zone_code")
    cropName = serializers.CharField(source="crop_name", allow_blank=True, required=False)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = Zone
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "zoneCode",
            "cropName",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "greenhouseName", "created_at", "updated_at")

    def validate(self, attrs):
        greenhouse = attrs.get("greenhouse") or getattr(self.instance, "greenhouse", None)
        zone_code = attrs.get("zone_code") or getattr(self.instance, "zone_code", None)
        if greenhouse and zone_code:
            qs = Zone.objects.filter(greenhouse=greenhouse, zone_code=zone_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"zoneCode": "同一温室内分区编码必须唯一"}
                )
        return attrs


class ClimateLogSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    recordedAt = serializers.DateTimeField(source="recorded_at")
    tempC = serializers.DecimalField(source="temp_c", max_digits=5, decimal_places=2)
    humidityPct = serializers.DecimalField(
        source="humidity_pct", max_digits=5, decimal_places=2
    )
    parUmol = serializers.DecimalField(
        source="par_umol", max_digits=8, decimal_places=2, required=False
    )
    co2Ppm = serializers.DecimalField(
        source="co2_ppm", max_digits=8, decimal_places=2, required=False
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = ClimateLog
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "recordedAt",
            "tempC",
            "humidityPct",
            "parUmol",
            "co2Ppm",
            "created_at",
        )
        read_only_fields = ("id", "zoneCode", "greenhouseName", "created_at")

    def validate_humidityPct(self, value):
        if value < 20 or value > 100:
            raise serializers.ValidationError("湿度须在 20～100 之间")
        return value


class IrrigationCycleSerializer(serializers.ModelSerializer):
    zoneId = serializers.PrimaryKeyRelatedField(
        source="zone", queryset=Zone.objects.all()
    )
    startAt = serializers.DateTimeField(source="start_at")
    durationMin = serializers.IntegerField(source="duration_min")
    waterLiters = serializers.DecimalField(
        source="water_liters", max_digits=10, decimal_places=2
    )
    zoneCode = serializers.CharField(source="zone.zone_code", read_only=True)
    greenhouseName = serializers.CharField(
        source="zone.greenhouse.name", read_only=True
    )

    class Meta:
        model = IrrigationCycle
        fields = (
            "id",
            "zoneId",
            "zoneCode",
            "greenhouseName",
            "startAt",
            "durationMin",
            "waterLiters",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "zoneCode",
            "greenhouseName",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        # 与防护领用互斥：温室存在开放领用单时，其下分区禁止新建轮灌（仅拦截新建）
        if self.instance is None:
            zone = attrs.get("zone")
            if zone and greenhouse_has_open_ppe_issue(zone.greenhouse_id):
                raise serializers.ValidationError(
                    {"zoneId": "该温室存在开放的喷药防护领用单，防护期间禁止新建轮灌"}
                )
        return attrs


class PpeIssueSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    workDate = serializers.DateField(source="work_date")
    suitCount = serializers.IntegerField(source="suit_count", min_value=1)
    maskCount = serializers.IntegerField(source="mask_count", min_value=1)
    greenhouseName = serializers.CharField(source="greenhouse.name", read_only=True)

    class Meta:
        model = PpeIssue
        fields = (
            "id",
            "greenhouseId",
            "greenhouseName",
            "workDate",
            "suitCount",
            "maskCount",
            "issuer",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "greenhouseName", "created_at", "updated_at")

    def validate(self, attrs):
        instance = self.instance
        greenhouse = attrs.get("greenhouse") or getattr(instance, "greenhouse", None)
        work_date = attrs.get("work_date") or getattr(instance, "work_date", None)
        status = attrs.get("status") or getattr(
            instance, "status", PpeIssue.STATUS_OPEN
        )

        # 同一温室同一作业日只允许一张开放单（与数据库部分唯一约束同口径）
        if status == PpeIssue.STATUS_OPEN and greenhouse and work_date:
            qs = open_ppe_issues().filter(greenhouse=greenhouse, work_date=work_date)
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"workDate": "同一温室同一作业日只允许一张开放防护领用单"}
                )

        # 已关单禁止修改数量
        if instance and instance.status == PpeIssue.STATUS_CLOSED:
            locked = {"suit_count": "suitCount", "mask_count": "maskCount"}
            for field, camel in locked.items():
                if field in attrs and attrs[field] != getattr(instance, field):
                    raise serializers.ValidationError(
                        {camel: "领用单已关，禁止修改数量"}
                    )
        return attrs
