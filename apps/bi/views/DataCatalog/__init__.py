from apps.bi.views.DataCatalog.CatalogAssets import (
    catalog_asset_list,
    catalog_asset_create,
    catalog_asset_detail,
    catalog_asset_edit,
    catalog_asset_delete,
    catalog_asset_certify,
    catalog_asset_deprecate,
)
from apps.bi.views.DataCatalog.CatalogLineageEdges import (
    catalog_lineage_edge_list,
    catalog_lineage_edge_create,
    catalog_lineage_edge_detail,
    catalog_lineage_edge_edit,
    catalog_lineage_edge_delete,
)
from apps.bi.views.DataCatalog.DataGovernancePolicies import (
    data_governance_policy_list,
    data_governance_policy_create,
    data_governance_policy_detail,
    data_governance_policy_edit,
    data_governance_policy_delete,
)
from apps.bi.views.DataCatalog.CatalogTrustEndorsements import (
    catalog_trust_endorsement_list,
    catalog_trust_endorsement_create,
    catalog_trust_endorsement_detail,
    catalog_trust_endorsement_edit,
    catalog_trust_endorsement_delete,
)
from apps.bi.views.DataCatalog.Overview import catalog_overview

__all__ = [
    "catalog_overview",
    "catalog_asset_list",
    "catalog_asset_create",
    "catalog_asset_detail",
    "catalog_asset_edit",
    "catalog_asset_delete",
    "catalog_asset_certify",
    "catalog_asset_deprecate",
    "catalog_lineage_edge_list",
    "catalog_lineage_edge_create",
    "catalog_lineage_edge_detail",
    "catalog_lineage_edge_edit",
    "catalog_lineage_edge_delete",
    "data_governance_policy_list",
    "data_governance_policy_create",
    "data_governance_policy_detail",
    "data_governance_policy_edit",
    "data_governance_policy_delete",
    "catalog_trust_endorsement_list",
    "catalog_trust_endorsement_create",
    "catalog_trust_endorsement_detail",
    "catalog_trust_endorsement_edit",
    "catalog_trust_endorsement_delete",
]
