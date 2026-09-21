from rest_framework import serializers

from .models import ClimateLog, Greenhouse, IrrigationCycle, PpeIssue, Zone


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
        # 与轮灌拦截、开放核对共用 PpeIssue.open_issues() 判定
        if hasattr(obj, "has_open_ppe_issue"):
            return obj.has_open_ppe_issue
        return PpeIssue.has_open_for_greenhouse(obj.id)


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
        # 互斥：温室存在开放防护领用时，其分区禁止新建轮灌（关闭后恢复）
        if self.instance is None:
            zone = attrs.get("zone")
            if zone and PpeIssue.has_open_for_greenhouse(zone.greenhouse_id):
                raise serializers.ValidationError(
                    {"zoneId": "该温室存在开放的喷药防护领用单，喷药作业期间禁止新建轮灌"}
                )
        return attrs


class PpeIssueSerializer(serializers.ModelSerializer):
    greenhouseId = serializers.PrimaryKeyRelatedField(
        source="greenhouse", queryset=Greenhouse.objects.all()
    )
    workDate = serializers.DateField(source="work_date")
    suitCount = serializers.IntegerField(source="suit_count", min_value=1)
    maskCount = serializers.IntegerField(source="mask_count", min_value=1)
    greenhouseName = serializers.CharField(
        source="greenhouse.name", read_only=True
    )

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
        # 关闭 DRF 由条件唯一约束自动生成的校验器，统一走下方 validate() 的中文提示
        validators = []

    def validate_suitCount(self, value):
        if value < 1:
            raise serializers.ValidationError("防护服件数须为正整数")
        return value

    def validate_maskCount(self, value):
        if value < 1:
            raise serializers.ValidationError("口罩件数须为正整数")
        return value

    def validate(self, attrs):
        instance = self.instance
        # 已关单禁止改数量
        if instance and instance.status == PpeIssue.STATUS_CLOSED:
            for field, label in (("suitCount", "防护服件数"), ("maskCount", "口罩件数")):
                model_field = self.fields[field].source
                if model_field in attrs and attrs[model_field] != getattr(instance, model_field):
                    raise serializers.ValidationError(
                        {field: f"领用单已关闭，{label}禁止修改"}
                    )

        greenhouse = attrs.get("greenhouse") or getattr(instance, "greenhouse", None)
        work_date = attrs.get("work_date") or getattr(instance, "work_date", None)
        status = attrs.get("status") or getattr(instance, "status", None)
        # 同温室同日只许一张开放单（与数据库部分唯一约束一致）
        if greenhouse and work_date and status == PpeIssue.STATUS_OPEN:
            qs = PpeIssue.open_issues().filter(
                greenhouse=greenhouse, work_date=work_date
            )
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"workDate": "同一温室同一作业日只允许一张开放领用单"}
                )
        return attrs
