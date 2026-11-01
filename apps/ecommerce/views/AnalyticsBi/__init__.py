from apps.ecommerce.views.AnalyticsBi.DailySalesSnapshots import (
    dailysalessnapshot_list,
    dailysalessnapshot_detail,
    dailysalessnapshot_create,
    dailysalessnapshot_edit,
    dailysalessnapshot_delete,
    dailysalessnapshot_generate,
)
from apps.ecommerce.views.AnalyticsBi.CustomerCohortMetrics import (
    customercohortmetric_list,
    customercohortmetric_detail,
    customercohortmetric_create,
    customercohortmetric_edit,
    customercohortmetric_delete,
    customercohortmetric_recalculate,
)
from apps.ecommerce.views.AnalyticsBi.ProductMerchandisingMetrics import (
    productmerchandisingmetric_list,
    productmerchandisingmetric_detail,
    productmerchandisingmetric_create,
    productmerchandisingmetric_edit,
    productmerchandisingmetric_delete,
    productmerchandisingmetric_reclassify,
)
from apps.ecommerce.views.AnalyticsBi.AttributionTouchpoints import (
    attributiontouchpoint_list,
    attributiontouchpoint_detail,
    attributiontouchpoint_create,
    attributiontouchpoint_edit,
    attributiontouchpoint_delete,
)
from apps.ecommerce.views.AnalyticsBi.AnalyticsCockpit import (
    analytics_cockpit,
)

__all__ = [
    "dailysalessnapshot_list",
    "dailysalessnapshot_detail",
    "dailysalessnapshot_create",
    "dailysalessnapshot_edit",
    "dailysalessnapshot_delete",
    "dailysalessnapshot_generate",
    "customercohortmetric_list",
    "customercohortmetric_detail",
    "customercohortmetric_create",
    "customercohortmetric_edit",
    "customercohortmetric_delete",
    "customercohortmetric_recalculate",
    "productmerchandisingmetric_list",
    "productmerchandisingmetric_detail",
    "productmerchandisingmetric_create",
    "productmerchandisingmetric_edit",
    "productmerchandisingmetric_delete",
    "productmerchandisingmetric_reclassify",
    "attributiontouchpoint_list",
    "attributiontouchpoint_detail",
    "attributiontouchpoint_create",
    "attributiontouchpoint_edit",
    "attributiontouchpoint_delete",
    "analytics_cockpit",
]
