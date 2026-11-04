from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.LakehouseZones import LakehouseZone
from apps.bi.models.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicy
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.views._common import bi_scope


@login_required
def warehouse_overview(request):
    tbl_stats = WarehouseTable.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        fact_count=Count("id", filter=Q(table_type="fact")),
        dim_count=Count("id", filter=Q(table_type="dimension")),
        total_rows=Sum("row_count"),
        total_compressed_bytes=Sum("compressed_bytes"),
    )

    mart_stats = DataMart.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        certified=Count("id", filter=Q(certification_status="certified")),
    )

    total_zones = LakehouseZone.objects.filter(tenant=request.tenant).count()
    total_policies = WarehouseStoragePolicy.objects.filter(tenant=request.tenant).count()

    recent_tables = (
        WarehouseTable.objects.filter(tenant=request.tenant)
        .select_related("lakehouse_zone", "data_mart")
        .order_by("-created_at")[:8]
    )

    marts = (
        DataMart.objects.filter(tenant=request.tenant)
        .annotate(table_count=Count("tables"))
        .order_by("-table_count")[:8]
    )

    zones = (
        LakehouseZone.objects.filter(tenant=request.tenant)
        .annotate(table_count=Count("tables"))
        .order_by("zone_type")
    )

    return render(
        request,
        "bi/data_warehouse/warehouse_overview.html",
        {
            "total_tables": tbl_stats["total"] or 0,
            "fact_count": tbl_stats["fact_count"] or 0,
            "dim_count": tbl_stats["dim_count"] or 0,
            "total_rows": tbl_stats["total_rows"] or 0,
            "total_compressed_bytes": tbl_stats["total_compressed_bytes"] or 0,
            "total_marts": mart_stats["total"] or 0,
            "certified_marts": mart_stats["certified"] or 0,
            "total_zones": total_zones,
            "total_policies": total_policies,
            "recent_tables": recent_tables,
            "marts": marts,
            "zones": zones,
        },
    )
