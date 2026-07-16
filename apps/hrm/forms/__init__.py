"""HRM forms package — split from apps/hrm/forms.py.

One sub-package per sub-module (3.1-3.41), one module per entity (mirrors models/, views/,
urls/). This __init__ re-exports every form.
"""
from ._common import *  # noqa: F401,F403

# 3.2 Organizational Structure
from .OrganizationalStructure.Jobgrade import (
    JobGradeForm,
)  # noqa: F401
from .OrganizationalStructure.Designation import (
    DesignationForm,
)  # noqa: F401
from .OrganizationalStructure.Department import (
    DepartmentProfileForm,
)  # noqa: F401
from .OrganizationalStructure.Costcenter import (
    CostCenterProfileForm,
)  # noqa: F401
from .OrganizationalStructure.EmployeeProfiles import (
    EmployeeProfileForm,
)  # noqa: F401
from .OrganizationalStructure.EmployeeDocuments import (
    EmployeeDocumentForm,
)  # noqa: F401
from .OrganizationalStructure.EmployeeLifecycleEvents import (
    EmployeeLifecycleEventForm,
)  # noqa: F401
from .OrganizationalStructure.LeaveTypes import (
    LeaveTypeForm,
)  # noqa: F401
from .OrganizationalStructure.LeaveAllocations import (
    LeaveAllocationForm,
)  # noqa: F401
from .OrganizationalStructure.LeaveRequests import (
    LeaveRequestForm,
)  # noqa: F401
from .OrganizationalStructure.LeaveEncashments import (
    LeaveEncashmentForm,
)  # noqa: F401

# 3.3 Employee Onboarding
from .EmployeeOnboarding.Template import (
    OnboardingTemplateForm,
)  # noqa: F401
from .EmployeeOnboarding.Templatetask import (
    OnboardingTemplateTaskForm,
)  # noqa: F401
from .EmployeeOnboarding.Program import (
    OnboardingProgramForm,
)  # noqa: F401
from .EmployeeOnboarding.Task import (
    OnboardingTaskForm,
)  # noqa: F401
from .EmployeeOnboarding.Document import (
    OnboardingDocumentForm,
)  # noqa: F401
from .EmployeeOnboarding.Assetallocation import (
    AssetAllocationForm,
)  # noqa: F401
from .EmployeeOnboarding.Orientationsession import (
    OrientationSessionForm,
)  # noqa: F401

# 3.4 Employee Offboarding
from .EmployeeOffboarding.Separationcase import (
    SeparationCaseForm,
)  # noqa: F401
from .EmployeeOffboarding.Exitinterview import (
    ExitInterviewForm,
)  # noqa: F401
from .EmployeeOffboarding.Clearanceitem import (
    ClearanceItemForm,
)  # noqa: F401
from .EmployeeOffboarding.Finalsettlement import (
    FinalSettlementForm,
)  # noqa: F401

# 3.5 Job Requisition
from .JobRequisition.Jobdescriptiontemplate import (
    JobDescriptionTemplateForm,
)  # noqa: F401
from .JobRequisition.Jobrequisition import (
    JobRequisitionForm,
)  # noqa: F401
from .JobRequisition.RequisitionApprovals import (
    RequisitionApprovalForm,
)  # noqa: F401

# 3.6 Candidate Management
from .CandidateManagement.Candidate import (
    CandidateTagForm,
    CandidateProfileForm,
    CandidateSkillForm,
)  # noqa: F401
from .CandidateManagement.Application import (
    JobApplicationForm,
    PublicApplicationForm,
)  # noqa: F401
from .CandidateManagement.Emailtemplate import (
    CandidateEmailTemplateForm,
)  # noqa: F401
from .CandidateManagement._helpers import (
    _validate_resume,
    _validate_upload,
)  # noqa: F401

# 3.7 Interview Process
from .InterviewProcess.Interview import (
    InterviewForm,
    InterviewPanelistForm,
)  # noqa: F401
from .InterviewProcess.Interviewfeedback import (
    InterviewFeedbackForm,
)  # noqa: F401
from .InterviewProcess.FeedbackCriterions import (
    FeedbackCriterionForm,
)  # noqa: F401

# 3.8 Offer Management
from .OfferManagement.Offerlettertemplate import (
    OfferLetterTemplateForm,
)  # noqa: F401
from .OfferManagement.Offer import (
    OfferForm,
    OfferApprovalForm,
)  # noqa: F401
from .OfferManagement.Backgroundverification import (
    BackgroundVerificationForm,
)  # noqa: F401
from .OfferManagement.PreboardingItems import (
    PreboardingItemForm,
)  # noqa: F401

# 3.11 Time Tracking
from .TimeTracking.Timesheet import (
    TimesheetForm,
)  # noqa: F401
from .TimeTracking.Timesheetentry import (
    TimesheetEntryForm,
)  # noqa: F401
from .TimeTracking.Overtimerequest import (
    OvertimeRequestForm,
)  # noqa: F401
from .TimeTracking.PublicHolidays import (
    PublicHolidayForm,
)  # noqa: F401
from .TimeTracking.HolidayPolicys import (
    HolidayPolicyForm,
)  # noqa: F401
from .TimeTracking.FloatingHolidayElections import (
    FloatingHolidayElectionForm,
)  # noqa: F401
from .TimeTracking.Shifts import (
    ShiftForm,
)  # noqa: F401
from .TimeTracking.ShiftAssignments import (
    ShiftAssignmentForm,
)  # noqa: F401
from .TimeTracking.AttendanceRecords import (
    AttendanceRecordForm,
)  # noqa: F401
from .TimeTracking.GeoFences import (
    GeoFenceForm,
)  # noqa: F401
from .TimeTracking.AttendanceRegularizations import (
    AttendanceRegularizationForm,
)  # noqa: F401

# 3.13 Salary Structure
from .SalaryStructure.Paycomponent import (
    PayComponentForm,
)  # noqa: F401
from .SalaryStructure.Salarystructuretemplate import (
    SalaryStructureTemplateForm,
)  # noqa: F401
from .SalaryStructure.SalaryStructureLines import (
    SalaryStructureLineForm,
)  # noqa: F401
from .SalaryStructure.Employeesalarystructure import (
    EmployeeSalaryStructureForm,
)  # noqa: F401

# 3.14 Payroll Processing
from .PayrollProcessing.Payrollcycle import (
    PayrollCycleForm,
)  # noqa: F401
from .PayrollProcessing.Payslip import (
    PayslipForm,
)  # noqa: F401

# 3.15 Statutory Compliance
from .StatutoryCompliance.Statutoryconfig import (
    StatutoryConfigForm,
)  # noqa: F401
from .StatutoryCompliance.Statutorystaterule import (
    StatutoryStateRuleForm,
)  # noqa: F401
from .StatutoryCompliance.Employeestatutoryidentifier import (
    EmployeeStatutoryIdentifierForm,
)  # noqa: F401
from .StatutoryCompliance.Statutoryreturn import (
    StatutoryReturnForm,
)  # noqa: F401

# 3.16 Tax & Investment
from .TaxInvestment.Taxregimeconfig import (
    TaxRegimeConfigForm,
)  # noqa: F401
from .TaxInvestment.TaxSlabBands import (
    TaxSlabBandForm,
)  # noqa: F401
from .TaxInvestment.Investmentdeclaration import (
    InvestmentDeclarationForm,
    InvestmentDeclarationLineForm,
)  # noqa: F401
from .TaxInvestment.Investmentproof import (
    InvestmentProofForm,
)  # noqa: F401
from .TaxInvestment.Taxcomputation import (
    TaxComputationForm,
)  # noqa: F401

# 3.17 Payout & Reports
from .PayoutReports.Payoutbatch import (
    PayoutBatchForm,
)  # noqa: F401
from .PayoutReports.Bankreconciliation import (
    BankReconciliationForm,
)  # noqa: F401

# 3.18 Goal Setting
from .GoalSetting.Goalperiod import (
    GoalPeriodForm,
)  # noqa: F401
from .GoalSetting.Objective import (
    ObjectiveForm,
)  # noqa: F401
from .GoalSetting.Keyresult import (
    KeyResultForm,
)  # noqa: F401
from .GoalSetting.Goalcheckin import (
    GoalCheckInForm,
)  # noqa: F401

# 3.19 Performance Review
from .PerformanceReview.Reviewcycle import (
    ReviewCycleForm,
)  # noqa: F401
from .PerformanceReview.Reviewtemplate import (
    ReviewTemplateForm,
)  # noqa: F401
from .PerformanceReview.Performancereview import (
    PerformanceReviewForm,
)  # noqa: F401
from .PerformanceReview.Calibrations import (
    CalibrationForm,
)  # noqa: F401
from .PerformanceReview.Reviewrating import (
    ReviewRatingForm,
)  # noqa: F401

# 3.20 Continuous Feedback
from .ContinuousFeedback.Kudosbadge import (
    KudosBadgeForm,
)  # noqa: F401
from .ContinuousFeedback.Feedback import (
    FeedbackForm,
)  # noqa: F401
from .ContinuousFeedback.Oneononemeeting import (
    OneOnOneMeetingForm,
)  # noqa: F401
from .ContinuousFeedback.Meetingactionitem import (
    MeetingActionItemForm,
)  # noqa: F401

# 3.21 Performance Improvement
from .PerformanceImprovement.PerformanceImprovementPlans import (
    PerformanceImprovementPlanForm,
)  # noqa: F401
from .PerformanceImprovement.Pipcheckin import (
    PIPCheckInForm,
)  # noqa: F401
from .PerformanceImprovement.Warningletter import (
    WarningLetterForm,
)  # noqa: F401
from .PerformanceImprovement.Coachingnote import (
    CoachingNoteForm,
)  # noqa: F401
from .PerformanceImprovement.Pip import (
    PIPCloseForm,
)  # noqa: F401
from .PerformanceImprovement.WarningAcknowledges import (
    WarningAcknowledgeForm,
)  # noqa: F401

# 3.22 Training Management
from .TrainingManagement.Trainingcourse import (
    TrainingCourseForm,
)  # noqa: F401
from .TrainingManagement.Trainingsession import (
    TrainingSessionForm,
)  # noqa: F401

# 3.23 Learning Management (LMS)
from .LearningManagement.ALLOWED_SCORM_EXTENSIONSs import (
    ALLOWED_SCORM_EXTENSIONS,
)  # noqa: F401
from .LearningManagement.MAX_SCORM_BYTESs import (
    MAX_SCORM_BYTES,
)  # noqa: F401
from .LearningManagement.ALLOWED_RESUME_EXTENSIONSs import (
    ALLOWED_RESUME_EXTENSIONS,
)  # noqa: F401
from .LearningManagement.MAX_RESUME_BYTESs import (
    MAX_RESUME_BYTES,
)  # noqa: F401
from .LearningManagement.ALLOWED_OFFER_DOC_EXTENSIONSs import (
    ALLOWED_OFFER_DOC_EXTENSIONS,
)  # noqa: F401
from .LearningManagement.ALLOWED_PREBOARDING_DOC_EXTENSIONSs import (
    ALLOWED_PREBOARDING_DOC_EXTENSIONS,
)  # noqa: F401
from .LearningManagement.MAX_OFFER_DOC_BYTESs import (
    MAX_OFFER_DOC_BYTES,
)  # noqa: F401
from .LearningManagement.Learningcontentitem import (
    LearningContentItemForm,
)  # noqa: F401
from .LearningManagement.Learningpath import (
    LearningPathForm,
)  # noqa: F401
from .LearningManagement.Learningpathitem import (
    LearningPathItemForm,
)  # noqa: F401
from .LearningManagement.Learningprogress import (
    LearningProgressForm,
)  # noqa: F401

# 3.24 Training Administration
from .TrainingAdministration.Trainingnomination import (
    TrainingNominationForm,
)  # noqa: F401
from .TrainingAdministration.Trainingattendance import (
    TrainingAttendanceForm,
)  # noqa: F401
from .TrainingAdministration.Trainingfeedback import (
    TrainingFeedbackForm,
)  # noqa: F401
from .TrainingAdministration.Trainingcertificate import (
    TrainingCertificateForm,
)  # noqa: F401

# 3.25 Personal Information
from .PersonalInformation.Emergencycontact import (
    EmergencyContactForm,
)  # noqa: F401
from .PersonalInformation.Employeebankaccount import (
    EmployeeBankAccountForm,
)  # noqa: F401
from .PersonalInformation.Familymember import (
    FamilyMemberForm,
    FamilyMemberChangeForm,
)  # noqa: F401
from .PersonalInformation.MyInfo import (
    EmployeeProfileMyInfoForm,
)  # noqa: F401
from .PersonalInformation._helpers import (
    _ThemedForm,
)  # noqa: F401
from .PersonalInformation.ProfileFieldChanges import (
    ProfileFieldChangeForm,
)  # noqa: F401
from .PersonalInformation.BankAccountChanges import (
    BankAccountChangeForm,
)  # noqa: F401

# 3.26 Request Management
from .RequestManagement.Documentrequest import (
    DocumentRequestForm,
)  # noqa: F401
from .RequestManagement.Idcardrequest import (
    IdCardRequestForm,
)  # noqa: F401
from .RequestManagement.Assetrequest import (
    AssetRequestForm,
)  # noqa: F401
from .RequestManagement.DocumentFulfills import (
    DocumentFulfillForm,
)  # noqa: F401

# 3.27 Communication Hub
from .CommunicationHub.Announcement import (
    AnnouncementForm,
)  # noqa: F401
from .CommunicationHub.Survey import (
    SurveyForm,
    SurveyActionPlanForm,
)  # noqa: F401
from .CommunicationHub.Suggestion import (
    SuggestionForm,
)  # noqa: F401
from .CommunicationHub.build_survey_response_forms import (
    build_survey_response_form,
)  # noqa: F401
from .CommunicationHub.HRDashboards import (
    HRDashboardForm,
)  # noqa: F401
from .CommunicationHub.HRDashboardWidgets import (
    HRDashboardWidgetForm,
)  # noqa: F401
from .CommunicationHub.Assets import (
    AssetForm,
)  # noqa: F401
from .CommunicationHub.AssetMaintenances import (
    AssetMaintenanceForm,
)  # noqa: F401
from .CommunicationHub.ExpenseCategorys import (
    ExpenseCategoryForm,
)  # noqa: F401
from .CommunicationHub.ExpenseClaims import (
    ExpenseClaimForm,
)  # noqa: F401
from .CommunicationHub.ExpenseClaimLines import (
    ExpenseClaimLineForm,
)  # noqa: F401
from .CommunicationHub.TravelPolicys import (
    TravelPolicyForm,
)  # noqa: F401
from .CommunicationHub.TravelRequests import (
    TravelRequestForm,
)  # noqa: F401
from .CommunicationHub.TravelBookings import (
    TravelBookingForm,
)  # noqa: F401
from .CommunicationHub._helpers import (
    _SLA_HOUR_PAIRS,
    _scope_currency,
)  # noqa: F401
from .CommunicationHub.HelpdeskSLAPolicys import (
    HelpdeskSLAPolicyForm,
)  # noqa: F401
from .CommunicationHub.HelpdeskCategorys import (
    HelpdeskCategoryForm,
)  # noqa: F401
from .CommunicationHub.HelpdeskTickets import (
    HelpdeskTicketForm,
)  # noqa: F401
from .CommunicationHub.KnowledgeArticles import (
    KnowledgeArticleForm,
)  # noqa: F401
from .CommunicationHub.SalaryBenchmarks import (
    SalaryBenchmarkForm,
)  # noqa: F401
from .CommunicationHub.BenefitPlans import (
    BenefitPlanForm,
)  # noqa: F401
from .CommunicationHub.EmployeeBenefitEnrollments import (
    EmployeeBenefitEnrollmentForm,
)  # noqa: F401
from .CommunicationHub.EquityGrants import (
    EquityGrantForm,
)  # noqa: F401
from .CommunicationHub.TalentPools import (
    TalentPoolForm,
)  # noqa: F401
from .CommunicationHub.TalentPoolMemberships import (
    TalentPoolMembershipForm,
)  # noqa: F401
from .CommunicationHub.SuccessionPlans import (
    SuccessionPlanForm,
)  # noqa: F401
from .CommunicationHub.SuccessionCandidates import (
    SuccessionCandidateForm,
)  # noqa: F401
from .CommunicationHub.ALLOWED_COMPLIANCE_DOC_EXTENSIONSs import (
    ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
)  # noqa: F401
from .CommunicationHub.MAX_COMPLIANCE_DOC_BYTESs import (
    MAX_COMPLIANCE_DOC_BYTES,
)  # noqa: F401
from .CommunicationHub.EmploymentContracts import (
    EmploymentContractForm,
)  # noqa: F401
from .CommunicationHub.HRPolicys import (
    HRPolicyForm,
)  # noqa: F401
from .CommunicationHub.Grievances import (
    GrievanceForm,
)  # noqa: F401
from .CommunicationHub.ComplianceRegisters import (
    ComplianceRegisterForm,
)  # noqa: F401
from .CommunicationHub.WorkforcePlans import (
    WorkforcePlanForm,
)  # noqa: F401
from .CommunicationHub.WorkforcePlanLines import (
    WorkforcePlanLineForm,
)  # noqa: F401
from .CommunicationHub.WorkforceScenarios import (
    WorkforceScenarioForm,
)  # noqa: F401
from .CommunicationHub.EmployeeSkills import (
    EmployeeSkillForm,
)  # noqa: F401
from .CommunicationHub.WellbeingPrograms import (
    WellbeingProgramForm,
)  # noqa: F401
from .CommunicationHub.WellbeingParticipations import (
    WellbeingParticipationForm,
)  # noqa: F401
from .CommunicationHub.FlexibleWorkArrangements import (
    FlexibleWorkArrangementForm,
)  # noqa: F401
