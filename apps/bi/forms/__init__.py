from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.forms.DataIntegration.CdcSyncConfigs import CdcSyncConfigForm
from apps.bi.forms.DataIntegration.DataSourceConnectors import DataSourceConnectorForm
from apps.bi.forms.DataIntegration.IngestionPipelines import IngestionPipelineForm
from apps.bi.forms.DataIntegration.IngestionRuns import IngestionRunForm
from apps.bi.forms.DataWarehouse.DataMarts import DataMartForm
from apps.bi.forms.DataWarehouse.LakehouseZones import LakehouseZoneForm
from apps.bi.forms.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicyForm
from apps.bi.forms.DataWarehouse.WarehouseTables import WarehouseTableForm
from apps.bi.forms.EtlPipelines.EtlPipelineRuns import EtlPipelineRunForm
from apps.bi.forms.EtlPipelines.EtlPipelines import EtlPipelineForm
from apps.bi.forms.EtlPipelines.EtlPipelineVersions import EtlPipelineVersionForm
from apps.bi.forms.EtlPipelines.TransformationSteps import TransformationStepForm
from apps.bi.forms.DataQuality.DataQualityExceptionForms import (
    DataQualityExceptionForm,
    DataQualityExceptionRemediationForm,
)
from apps.bi.forms.DataQuality.DataQualityProfileForms import DataQualityProfileForm
from apps.bi.forms.DataQuality.DataQualityRuleForms import DataQualityRuleForm
from apps.bi.forms.DataQuality.DataQualityScorecardForms import DataQualityScorecardForm
from apps.bi.forms.MasterData.MdmGoldenRecordForms import (
    MdmGoldenRecordForm,
    MdmGoldenRecordMergeForm,
)
from apps.bi.forms.MasterData.MdmHierarchyNodeForms import MdmHierarchyNodeForm
from apps.bi.forms.MasterData.MdmReferenceCodeForms import MdmReferenceCodeForm
from apps.bi.forms.MasterData.MdmSurvivorshipRuleForms import MdmSurvivorshipRuleForm
from apps.bi.forms.DataCatalog.CatalogAssets import (
    CatalogAssetForm,
    CatalogAssetCertifyForm,
    CatalogAssetDeprecateForm,
)
from apps.bi.forms.DataCatalog.CatalogLineageEdges import CatalogLineageEdgeForm
from apps.bi.forms.DataCatalog.DataGovernancePolicies import DataGovernancePolicyForm
from apps.bi.forms.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsementForm
from apps.bi.forms.Dashboards.BiDashboardBookmarkForms import BiDashboardBookmarkForm
from apps.bi.forms.Dashboards.BiDashboardFilterForms import BiDashboardFilterForm
from apps.bi.forms.Dashboards.BiDashboardForms import (
    BiDashboardDuplicateForm,
    BiDashboardForm,
)
from apps.bi.forms.Dashboards.BiDashboardWidgetForms import (
    BiDashboardWidgetForm,
    BiDashboardWidgetPositionForm,
)
from apps.bi.forms.OlapAnalysis import (
    OlapCubeForm,
    PivotAnalysisViewForm,
    ScenarioWritebackCellForm,
    WhatIfScenarioForm,
)
from apps.bi.forms.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsightForm
from apps.bi.forms.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestionForm
from apps.bi.forms.AiAugmentedAnalytics.TextSentimentAnalyses import TextSentimentAnalysisForm
from apps.bi.forms.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendationForm
from apps.bi.forms.OperationalReporting.ReportDefinitions import (
    ReportCloneForm,
    ReportDefinitionForm,
)
from apps.bi.forms.OperationalReporting.ReportDrillPaths import ReportDrillPathForm
from apps.bi.forms.OperationalReporting.ReportExecutions import ReportExecutionRunForm
from apps.bi.forms.OperationalReporting.ReportParameters import ReportParameterForm
from apps.bi.forms.PerformanceScorecards import (
    KpiDefinitionForm,
    KpiDefinitionRefreshForm,
    PerformanceScorecardForm,
    PerformanceScorecardRecalculateForm,
    ScorecardKpiAssignmentForm,
    ScorecardKpiRecordActualForm,
    StrategicObjectiveForm,
)
from apps.bi.forms.SelfServiceAnalytics.AdHocCalculatedFields import (
    AdHocCalculatedFieldForm,
)
from apps.bi.forms.SelfServiceAnalytics.AdHocQueries import (
    AdHocQueryComposerForm,
    AdHocQueryForm,
)
from apps.bi.forms.SelfServiceAnalytics.DataBlendDefinitions import (
    DataBlendDefinitionForm,
)
from apps.bi.forms.SelfServiceAnalytics.SavedAnalysisViews import (
    SavedAnalysisViewForm,
    SavedAnalysisViewShareForm,
)
from apps.bi.forms.SemanticLayer.BusinessGlossaryTerms import (
    BusinessGlossaryTermCertificationForm,
    BusinessGlossaryTermForm,
)
from apps.bi.forms.SemanticLayer.CalculatedMeasureForms import CalculatedMeasureForm
from apps.bi.forms.SemanticLayer.DrillHierarchyForms import DrillHierarchyForm
from apps.bi.forms.SemanticLayer.SemanticModels import (
    SemanticModelCertificationForm,
    SemanticModelForm,
)

__all__ = [
    "TenantUniqueMixin",
    "reject_foreign",
    "DataSourceConnectorForm",
    "IngestionPipelineForm",
    "CdcSyncConfigForm",
    "IngestionRunForm",
    "EtlPipelineForm",
    "TransformationStepForm",
    "EtlPipelineVersionForm",
    "EtlPipelineRunForm",
    "DataMartForm",
    "LakehouseZoneForm",
    "WarehouseStoragePolicyForm",
    "WarehouseTableForm",
    "SemanticModelForm",
    "SemanticModelCertificationForm",
    "BusinessGlossaryTermForm",
    "BusinessGlossaryTermCertificationForm",
    "CalculatedMeasureForm",
    "DrillHierarchyForm",
    "DataQualityProfileForm",
    "DataQualityRuleForm",
    "DataQualityExceptionForm",
    "DataQualityExceptionRemediationForm",
    "DataQualityScorecardForm",
    "MdmGoldenRecordForm",
    "MdmGoldenRecordMergeForm",
    "MdmSurvivorshipRuleForm",
    "MdmHierarchyNodeForm",
    "MdmReferenceCodeForm",
    "CatalogAssetForm",
    "CatalogAssetCertifyForm",
    "CatalogAssetDeprecateForm",
    "CatalogLineageEdgeForm",
    "DataGovernancePolicyForm",
    "CatalogTrustEndorsementForm",
    "BiDashboardForm",
    "BiDashboardDuplicateForm",
    "BiDashboardWidgetForm",
    "BiDashboardWidgetPositionForm",
    "BiDashboardBookmarkForm",
    "BiDashboardFilterForm",
    "ReportDefinitionForm",
    "ReportCloneForm",
    "ReportParameterForm",
    "ReportExecutionRunForm",
    "ReportDrillPathForm",
    "AdHocQueryForm",
    "AdHocQueryComposerForm",
    "AdHocCalculatedFieldForm",
    "DataBlendDefinitionForm",
    "SavedAnalysisViewForm",
    "SavedAnalysisViewShareForm",
    "KpiDefinitionForm",
    "KpiDefinitionRefreshForm",
    "PerformanceScorecardForm",
    "PerformanceScorecardRecalculateForm",
    "ScorecardKpiAssignmentForm",
    "ScorecardKpiRecordActualForm",
    "StrategicObjectiveForm",
    "OlapCubeForm",
    "PivotAnalysisViewForm",
    "WhatIfScenarioForm",
    "ScenarioWritebackCellForm",
    "AugmentedInsightForm",
    "SmartDataPrepSuggestionForm",
    "TextSentimentAnalysisForm",
    "AnalyticsRecommendationForm",
]
