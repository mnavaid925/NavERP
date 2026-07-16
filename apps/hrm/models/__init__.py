"""HRM models package — split from apps/hrm/models.py.

One sub-package per NavERP sub-module (3.1-3.41), one module per entity (mirrors forms/,
views/, urls/). This __init__ re-exports every model + the shared base, so
``from apps.hrm.models import EmployeeProfile`` is unchanged.
"""
from ._base import *  # noqa: F401,F403
from ._base import _advance_months, _json_safe  # noqa: F401

# 3.1 Employee Management
from .EmployeeManagement.EmployeeProfiles import (
    EmployeeProfile,
)  # noqa: F401
from .EmployeeManagement.Document import (
    EmployeeDocument,
)  # noqa: F401
from .EmployeeManagement.Lifecycle import (
    LIFECYCLE_EVENT_TYPE_CHOICES,
)  # noqa: F401
from .EmployeeManagement.EmployeeLifecycleEvents import (
    EmployeeLifecycleEvent,
)  # noqa: F401

# 3.2 Organizational Structure
from .OrganizationalStructure.Jobgrade import (
    JobGrade,
)  # noqa: F401
from .OrganizationalStructure.Designation import (
    Designation,
)  # noqa: F401
from .OrganizationalStructure.Department import (
    DepartmentProfile,
)  # noqa: F401
from .OrganizationalStructure.Costcenter import (
    CostCenterProfile,
)  # noqa: F401

# 3.3 Employee Onboarding
from .EmployeeOnboarding.Task import (
    TASK_CATEGORY_CHOICES,
    OnboardingTask,
)  # noqa: F401
from .EmployeeOnboarding.ASSIGNEE_ROLE_CHOICESs import (
    ASSIGNEE_ROLE_CHOICES,
)  # noqa: F401
from .EmployeeOnboarding.PHASE_CHOICESs import (
    PHASE_CHOICES,
)  # noqa: F401
from .EmployeeOnboarding.Template import (
    OnboardingTemplate,
)  # noqa: F401
from .EmployeeOnboarding.Templatetask import (
    OnboardingTemplateTask,
)  # noqa: F401
from .EmployeeOnboarding.Program import (
    OnboardingProgram,
)  # noqa: F401
from .EmployeeOnboarding.Document import (
    OnboardingDocument,
)  # noqa: F401
from .EmployeeOnboarding.Assetallocation import (
    AssetAllocation,
)  # noqa: F401
from .EmployeeOnboarding.Orientationsession import (
    OrientationSession,
)  # noqa: F401

# 3.4 Employee Offboarding
from .EmployeeOffboarding._helpers import (
    _RATING_VALIDATORS,
)  # noqa: F401
from .EmployeeOffboarding.Separationcase import (
    SeparationCase,
)  # noqa: F401
from .EmployeeOffboarding.Exitinterview import (
    ExitInterview,
)  # noqa: F401
from .EmployeeOffboarding.Clearanceitem import (
    ClearanceItem,
)  # noqa: F401
from .EmployeeOffboarding.Finalsettlement import (
    FinalSettlement,
)  # noqa: F401

# 3.5 Job Requisition
from .JobRequisition.EMPLOYMENT_TYPE_CHOICESs import (
    EMPLOYMENT_TYPE_CHOICES,
)  # noqa: F401
from .JobRequisition.REQ_TYPE_CHOICESs import (
    REQ_TYPE_CHOICES,
)  # noqa: F401
from .JobRequisition.REASON_FOR_HIRE_CHOICESs import (
    REASON_FOR_HIRE_CHOICES,
)  # noqa: F401
from .JobRequisition.POSTING_TYPE_CHOICESs import (
    POSTING_TYPE_CHOICES,
)  # noqa: F401
from .JobRequisition.PRIORITY_CHOICESs import (
    PRIORITY_CHOICES,
)  # noqa: F401
from .JobRequisition.JR_STATUS_CHOICESs import (
    JR_STATUS_CHOICES,
)  # noqa: F401
from .JobRequisition.APPROVAL_STEP_STATUS_CHOICESs import (
    APPROVAL_STEP_STATUS_CHOICES,
)  # noqa: F401
from .JobRequisition.APPROVER_ROLE_CHOICESs import (
    APPROVER_ROLE_CHOICES,
)  # noqa: F401
from .JobRequisition.Jobdescriptiontemplate import (
    JobDescriptionTemplate,
)  # noqa: F401
from .JobRequisition.Jobrequisition import (
    JobRequisition,
)  # noqa: F401

# 3.6 Candidate Management
from .CandidateManagement.RequisitionApprovals import (
    RequisitionApproval,
)  # noqa: F401
from .CandidateManagement.HEX_COLOR_VALIDATORs import (
    HEX_COLOR_VALIDATOR,
)  # noqa: F401
from .CandidateManagement.Candidate import (
    CANDIDATE_STATUS_CHOICES,
    CANDIDATE_GENDER_CHOICES,
    CANDIDATE_SOURCE_CHOICES,
    CandidateTag,
    CandidateProfile,
    CandidateSkill,
)  # noqa: F401
from .CandidateManagement.QUALIFICATION_CHOICESs import (
    QUALIFICATION_CHOICES,
)  # noqa: F401
from .CandidateManagement.SKILL_PROFICIENCY_CHOICESs import (
    SKILL_PROFICIENCY_CHOICES,
)  # noqa: F401
from .CandidateManagement.SKILL_SOURCE_CHOICESs import (
    SKILL_SOURCE_CHOICES,
)  # noqa: F401
from .CandidateManagement.Application import (
    APPLICATION_STAGE_CHOICES,
    APPLICATION_TERMINAL_STAGES,
    JobApplication,
)  # noqa: F401
from .CandidateManagement.REJECTION_REASON_CHOICESs import (
    REJECTION_REASON_CHOICES,
)  # noqa: F401
from .CandidateManagement.EMAIL_TEMPLATE_TYPE_CHOICESs import (
    EMAIL_TEMPLATE_TYPE_CHOICES,
)  # noqa: F401
from .CandidateManagement.Communication import (
    COMMUNICATION_CHANNEL_CHOICES,
    COMMUNICATION_DIRECTION_CHOICES,
    CandidateCommunication,
)  # noqa: F401
from .CandidateManagement.DELIVERY_STATUS_CHOICESs import (
    DELIVERY_STATUS_CHOICES,
)  # noqa: F401
from .CandidateManagement.Emailtemplate import (
    CandidateEmailTemplate,
)  # noqa: F401

# 3.7 Interview Process
from .InterviewProcess.Interview import (
    INTERVIEW_MODE_CHOICES,
    INTERVIEW_STATUS_CHOICES,
    INTERVIEW_TERMINAL_STATUSES,
    Interview,
    InterviewPanelist,
)  # noqa: F401
from .InterviewProcess.VIDEO_PROVIDER_CHOICESs import (
    VIDEO_PROVIDER_CHOICES,
)  # noqa: F401
from .InterviewProcess.PANELIST_ROLE_CHOICESs import (
    PANELIST_ROLE_CHOICES,
)  # noqa: F401
from .InterviewProcess.RSVP_STATUS_CHOICESs import (
    RSVP_STATUS_CHOICES,
)  # noqa: F401
from .InterviewProcess.RECOMMENDATION_CHOICESs import (
    RECOMMENDATION_CHOICES,
)  # noqa: F401
from .InterviewProcess.Interviewfeedback import (
    InterviewFeedback,
)  # noqa: F401
from .InterviewProcess.FeedbackCriterions import (
    FeedbackCriterion,
)  # noqa: F401

# 3.8 Offer Management
from .OfferManagement.Offer import (
    OFFER_STATUS_CHOICES,
    OFFER_TERMINAL_STATUSES,
    OFFER_DECLINE_REASON_CHOICES,
    Offer,
    OfferApproval,
)  # noqa: F401
from .OfferManagement.SIGNATURE_STATUS_CHOICESs import (
    SIGNATURE_STATUS_CHOICES,
)  # noqa: F401
from .OfferManagement.BGV_VENDOR_CHOICESs import (
    BGV_VENDOR_CHOICES,
)  # noqa: F401
from .OfferManagement.BGV_CHECK_TYPE_CHOICESs import (
    BGV_CHECK_TYPE_CHOICES,
)  # noqa: F401
from .OfferManagement.BGV_STATUS_CHOICESs import (
    BGV_STATUS_CHOICES,
)  # noqa: F401
from .OfferManagement.BGV_RESULT_CHOICESs import (
    BGV_RESULT_CHOICES,
)  # noqa: F401
from .OfferManagement.BGV_MANUAL_TRANSITION_STATUSESs import (
    BGV_MANUAL_TRANSITION_STATUSES,
)  # noqa: F401
from .OfferManagement.PREBOARDING_DOC_TYPE_CHOICESs import (
    PREBOARDING_DOC_TYPE_CHOICES,
)  # noqa: F401
from .OfferManagement.PREBOARDING_STATUS_CHOICESs import (
    PREBOARDING_STATUS_CHOICES,
)  # noqa: F401
from .OfferManagement.Offerlettertemplate import (
    OfferLetterTemplate,
)  # noqa: F401
from .OfferManagement.Backgroundverification import (
    BackgroundVerification,
)  # noqa: F401
from .OfferManagement.PreboardingItems import (
    PreboardingItem,
)  # noqa: F401

# 3.9 Attendance Management
from .AttendanceManagement.Shift import (
    Shift,
)  # noqa: F401
from .AttendanceManagement.Shiftassignment import (
    ShiftAssignment,
)  # noqa: F401
from .AttendanceManagement.Record import (
    AttendanceRecord,
)  # noqa: F401
from .AttendanceManagement.Geofence import (
    GeoFence,
)  # noqa: F401
from .AttendanceManagement.Regularization import (
    AttendanceRegularization,
)  # noqa: F401

# 3.10 Leave Management
from .LeaveManagement.Type import (
    LeaveType,
)  # noqa: F401
from .LeaveManagement.Allocation import (
    LeaveAllocation,
)  # noqa: F401
from .LeaveManagement.Request import (
    LeaveRequest,
)  # noqa: F401
from .LeaveManagement.Encashment import (
    LeaveEncashment,
)  # noqa: F401

# 3.11 Time Tracking
from .TimeTracking.Timesheet import (
    Timesheet,
)  # noqa: F401
from .TimeTracking.Timesheetentry import (
    TimesheetEntry,
)  # noqa: F401
from .TimeTracking.Overtimerequest import (
    OvertimeRequest,
)  # noqa: F401

# 3.12 Holiday Management
from .HolidayManagement.Publicholiday import (
    PublicHoliday,
)  # noqa: F401
from .HolidayManagement.Holidaypolicy import (
    HolidayPolicy,
)  # noqa: F401
from .HolidayManagement.Floatingholidayelection import (
    FloatingHolidayElection,
)  # noqa: F401

# 3.13 Salary Structure
from .SalaryStructure.Paycomponent import (
    PayComponent,
)  # noqa: F401
from .SalaryStructure.Salarystructuretemplate import (
    SalaryStructureTemplate,
)  # noqa: F401
from .SalaryStructure.SalaryStructureLines import (
    SalaryStructureLine,
)  # noqa: F401
from .SalaryStructure.Employeesalarystructure import (
    EmployeeSalaryStructure,
)  # noqa: F401

# 3.14 Payroll Processing
from .PayrollProcessing.Payrollcycle import (
    PayrollCycle,
)  # noqa: F401
from .PayrollProcessing.Payslip import (
    Payslip,
    PayslipLine,
)  # noqa: F401

# 3.15 Statutory Compliance
from .StatutoryCompliance.INDIAN_STATE_CHOICESs import (
    INDIAN_STATE_CHOICES,
)  # noqa: F401
from .StatutoryCompliance.Statutoryconfig import (
    StatutoryConfig,
)  # noqa: F401
from .StatutoryCompliance.Statutorystaterule import (
    StatutoryStateRule,
)  # noqa: F401
from .StatutoryCompliance.Employeestatutoryidentifier import (
    EmployeeStatutoryIdentifier,
)  # noqa: F401
from .StatutoryCompliance.Statutoryreturn import (
    StatutoryReturn,
)  # noqa: F401

# 3.16 Tax & Investment
from .TaxInvestment.NEW_REGIME_ALLOWED_SECTIONSs import (
    NEW_REGIME_ALLOWED_SECTIONS,
)  # noqa: F401
from .TaxInvestment.SECTION_CAPSs import (
    SECTION_CAPS,
)  # noqa: F401
from .TaxInvestment._helpers import (
    _progressive_tax,
)  # noqa: F401
from .TaxInvestment.Taxregimeconfig import (
    TaxRegimeConfig,
)  # noqa: F401
from .TaxInvestment.TaxSlabBands import (
    TaxSlabBand,
)  # noqa: F401
from .TaxInvestment.Investmentdeclaration import (
    InvestmentDeclaration,
    InvestmentDeclarationLine,
)  # noqa: F401
from .TaxInvestment.Investmentproof import (
    InvestmentProof,
)  # noqa: F401
from .TaxInvestment.Taxcomputation import (
    TaxComputation,
)  # noqa: F401

# 3.17 Payout & Reports
from .PayoutReports.Payoutbatch import (
    PayoutBatch,
)  # noqa: F401
from .PayoutReports.PayoutPayments import (
    PayoutPayment,
)  # noqa: F401
from .PayoutReports.Payslipdistribution import (
    PayslipDistribution,
)  # noqa: F401
from .PayoutReports.Bankreconciliation import (
    BankReconciliation,
)  # noqa: F401

# 3.18 Goal Setting
from .GoalSetting._helpers import (
    _clamp_pct,
    _pace_health,
    _HEALTH_LABELS,
)  # noqa: F401
from .GoalSetting.Goalperiod import (
    GoalPeriod,
)  # noqa: F401
from .GoalSetting.Objective import (
    Objective,
)  # noqa: F401
from .GoalSetting.Keyresult import (
    KeyResult,
)  # noqa: F401
from .GoalSetting.Goalcheckin import (
    GoalCheckIn,
)  # noqa: F401

# 3.19 Performance Review
from .PerformanceReview.REVIEW_TYPE_CHOICESs import (
    REVIEW_TYPE_CHOICES,
)  # noqa: F401
from .PerformanceReview.Reviewcycle import (
    ReviewCycle,
)  # noqa: F401
from .PerformanceReview.Reviewtemplate import (
    ReviewTemplate,
)  # noqa: F401
from .PerformanceReview.Performancereview import (
    PerformanceReview,
)  # noqa: F401
from .PerformanceReview.Reviewrating import (
    ReviewRating,
)  # noqa: F401

# 3.20 Continuous Feedback
from .ContinuousFeedback.Kudosbadge import (
    KudosBadge,
)  # noqa: F401
from .ContinuousFeedback.Feedback import (
    Feedback,
)  # noqa: F401
from .ContinuousFeedback.Oneononemeeting import (
    OneOnOneMeeting,
)  # noqa: F401
from .ContinuousFeedback.Meetingactionitem import (
    MeetingActionItem,
)  # noqa: F401

# 3.21 Performance Improvement
from .PerformanceImprovement.PerformanceImprovementPlans import (
    PerformanceImprovementPlan,
)  # noqa: F401
from .PerformanceImprovement.Pipcheckin import (
    PIPCheckIn,
)  # noqa: F401
from .PerformanceImprovement.Warningletter import (
    WarningLetter,
)  # noqa: F401
from .PerformanceImprovement.Coachingnote import (
    CoachingNote,
)  # noqa: F401

# 3.22 Training Management
from .TrainingManagement.Trainingcourse import (
    TrainingCourse,
)  # noqa: F401
from .TrainingManagement.Trainingsession import (
    TrainingSession,
)  # noqa: F401

# 3.23 Learning Management (LMS)
from .LearningManagement.Learningcontentitem import (
    LearningContentItem,
)  # noqa: F401
from .LearningManagement.Learningpath import (
    LearningPath,
)  # noqa: F401
from .LearningManagement.Learningpathitem import (
    LearningPathItem,
)  # noqa: F401
from .LearningManagement.Learningprogress import (
    LearningProgress,
)  # noqa: F401

# 3.24 Training Administration
from .TrainingAdministration.Trainingnomination import (
    TrainingNomination,
)  # noqa: F401
from .TrainingAdministration.Trainingattendance import (
    TrainingAttendance,
)  # noqa: F401
from .TrainingAdministration.Trainingfeedback import (
    TrainingFeedback,
)  # noqa: F401
from .TrainingAdministration.Trainingcertificate import (
    TrainingCertificate,
)  # noqa: F401

# 3.25 Personal Information
from .PersonalInformation.Emergencycontact import (
    EmergencyContact,
)  # noqa: F401
from .PersonalInformation.Employeebankaccount import (
    EmployeeBankAccount,
)  # noqa: F401
from .PersonalInformation.Familymember import (
    FamilyMember,
)  # noqa: F401
from .PersonalInformation.Changerequest import (
    EmployeeInfoChangeRequest,
)  # noqa: F401

# 3.26 Request Management
from .RequestManagement.Documentrequest import (
    DocumentRequest,
)  # noqa: F401
from .RequestManagement.Idcardrequest import (
    IdCardRequest,
)  # noqa: F401
from .RequestManagement.Assetrequest import (
    AssetRequest,
)  # noqa: F401

# 3.27 Communication Hub
from .CommunicationHub.Announcement import (
    Announcement,
)  # noqa: F401
from .CommunicationHub.Survey import (
    Survey,
    SurveyResponse,
)  # noqa: F401
from .CommunicationHub.Suggestion import (
    Suggestion,
)  # noqa: F401

# 3.32 Analytics Dashboard
from .AnalyticsDashboard.ANALYTICS_RANGE_CHOICESs import (
    ANALYTICS_RANGE_CHOICES,
)  # noqa: F401
from .AnalyticsDashboard.Dashboard import (
    DASHBOARD_LAYOUT_CHOICES,
    HRDashboard,
)  # noqa: F401
from .AnalyticsDashboard.Widget import (
    WIDGET_CHART_CHOICES,
    WIDGET_SIZE_CHOICES,
    WIDGET_METRIC_CHOICES,
    HRDashboardWidget,
)  # noqa: F401

# 3.33 Asset Management
from .AssetManagement.Asset import (
    Asset,
)  # noqa: F401
from .AssetManagement.Assetmaintenance import (
    AssetMaintenance,
)  # noqa: F401

# 3.34 Expense Management
from .ExpenseManagement.Expensecategory import (
    ExpenseCategory,
)  # noqa: F401
from .ExpenseManagement.Expenseclaim import (
    ExpenseClaim,
)  # noqa: F401
from .ExpenseManagement.Expenseclaimline import (
    ExpenseClaimLine,
)  # noqa: F401

# 3.35 Travel Management
from .TravelManagement._helpers import (
    _TRAVEL_CLASS_RANK,
)  # noqa: F401
from .TravelManagement.Travelpolicy import (
    TravelPolicy,
)  # noqa: F401
from .TravelManagement.Travelrequest import (
    TravelRequest,
)  # noqa: F401
from .TravelManagement.Travelbooking import (
    TravelBooking,
)  # noqa: F401

# 3.36 Helpdesk
from .Helpdesk.Helpdeskslapolicy import (
    HelpdeskSLAPolicy,
)  # noqa: F401
from .Helpdesk.Helpdeskcategory import (
    HelpdeskCategory,
)  # noqa: F401
from .Helpdesk.Helpdeskticket import (
    HelpdeskTicket,
)  # noqa: F401
from .Helpdesk.Knowledgearticle import (
    KnowledgeArticle,
)  # noqa: F401

# 3.37 Compensation & Benefits
from .CompensationBenefits.Salarybenchmark import (
    SalaryBenchmark,
)  # noqa: F401
from .CompensationBenefits.Benefitplan import (
    BenefitPlan,
)  # noqa: F401
from .CompensationBenefits.Employeebenefitenrollment import (
    EmployeeBenefitEnrollment,
)  # noqa: F401
from .CompensationBenefits.Equitygrant import (
    EquityGrant,
)  # noqa: F401

# 3.38 Talent Management & Succession
from .TalentManagement._helpers import (
    _rating_band,
    _NINE_BOX_LABELS,
)  # noqa: F401
from .TalentManagement.Talentpool import (
    TalentPool,
)  # noqa: F401
from .TalentManagement.Talentpoolmembership import (
    TalentPoolMembership,
)  # noqa: F401
from .TalentManagement.Successionplan import (
    SuccessionPlan,
)  # noqa: F401
from .TalentManagement.Successioncandidate import (
    SuccessionCandidate,
)  # noqa: F401

# 3.39 Compliance & Legal
from .ComplianceLegal.Employmentcontract import (
    EmploymentContract,
)  # noqa: F401
from .ComplianceLegal.Hrpolicy import (
    HRPolicy,
)  # noqa: F401
from .ComplianceLegal.Policyacknowledgment import (
    PolicyAcknowledgment,
)  # noqa: F401
from .ComplianceLegal.Grievance import (
    Grievance,
)  # noqa: F401
from .ComplianceLegal.Complianceregister import (
    ComplianceRegister,
)  # noqa: F401

# 3.40 Workforce Planning
from .WorkforcePlanning.Workforceplan import (
    WorkforcePlan,
)  # noqa: F401
from .WorkforcePlanning.Workforceplanline import (
    WorkforcePlanLine,
)  # noqa: F401
from .WorkforcePlanning.Workforcescenario import (
    WorkforceScenario,
)  # noqa: F401
from .WorkforcePlanning.Employeeskill import (
    EmployeeSkill,
)  # noqa: F401

# 3.41 Employee Engagement & Wellbeing
from .EmployeeEngagement.Surveyactionplan import (
    SurveyActionPlan,
)  # noqa: F401
from .EmployeeEngagement.Wellbeingprogram import (
    WellbeingProgram,
)  # noqa: F401
from .EmployeeEngagement.Wellbeingparticipation import (
    WellbeingParticipation,
)  # noqa: F401
from .EmployeeEngagement.Flexibleworkarrangement import (
    FlexibleWorkArrangement,
)  # noqa: F401
