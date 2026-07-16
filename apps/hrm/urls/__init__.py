"""HRM URLconf package — split from the former monolithic apps/hrm/urls.py.

One sub-package per NavERP sub-module (3.1-3.41), one module per entity, mirroring
apps/hrm/views/. Each entity module exposes its own ``urlpatterns``; this __init__
concatenates them GROUPED BY ENTITY and keeps ``app_name = "hrm"``, so every ``hrm:<name>``
   reverse and ``include("apps.hrm.urls")`` in config/urls.py is unchanged.

Django is first-match-wins, so ORDER IS BEHAVIOUR. Grouping by entity is not necessarily the
monolith's exact sequence; the split was verified to leave every route's resolve()/reverse()
identical. When you ADD a greedy-converter route, check it against the whole list below.
"""
from .EmployeeManagement.HrmOverview import urlpatterns as _employeemanagement_hrmoverview
from .OrganizationalStructure.Designation import urlpatterns as _organizationalstructure_designation
from .OrganizationalStructure.Jobgrade import urlpatterns as _organizationalstructure_jobgrade
from .OrganizationalStructure.Department import urlpatterns as _organizationalstructure_department
from .OrganizationalStructure.Costcenter import urlpatterns as _organizationalstructure_costcenter
from .OrganizationalStructure.OrgChart import urlpatterns as _organizationalstructure_orgchart
from .OrganizationalStructure.CompanySetup import urlpatterns as _organizationalstructure_companysetup
from .EmployeeManagement.List import urlpatterns as _employeemanagement_list
from .EmployeeManagement.Form import urlpatterns as _employeemanagement_form
from .EmployeeManagement.Detail import urlpatterns as _employeemanagement_detail
from .EmployeeManagement.Document import urlpatterns as _employeemanagement_document
from .EmployeeManagement.Lifecycle import urlpatterns as _employeemanagement_lifecycle
from .LeaveManagement.Type import urlpatterns as _leavemanagement_type
from .LeaveManagement.Allocation import urlpatterns as _leavemanagement_allocation
from .LeaveManagement.Request import urlpatterns as _leavemanagement_request
from .LeaveManagement.Encashment import urlpatterns as _leavemanagement_encashment
from .LeaveManagement.Policy import urlpatterns as _leavemanagement_policy
from .TimeTracking.Timesheet import urlpatterns as _timetracking_timesheet
from .TimeTracking.Timesheetentry import urlpatterns as _timetracking_timesheetentry
from .TimeTracking.Overtimerequest import urlpatterns as _timetracking_overtimerequest
from .TimeTracking.UtilizationReport import urlpatterns as _timetracking_utilizationreport
from .TimeTracking.ProjectTimeReport import urlpatterns as _timetracking_projecttimereport
from .HolidayManagement.Publicholiday import urlpatterns as _holidaymanagement_publicholiday
from .HolidayManagement.Holidaypolicy import urlpatterns as _holidaymanagement_holidaypolicy
from .HolidayManagement.Floatingholidayelection import urlpatterns as _holidaymanagement_floatingholidayelection
from .SalaryStructure.Paycomponent import urlpatterns as _salarystructure_paycomponent
from .SalaryStructure.Salarystructuretemplate import urlpatterns as _salarystructure_salarystructuretemplate
from .SalaryStructure.Employeesalarystructure import urlpatterns as _salarystructure_employeesalarystructure
from .PayrollProcessing.Payrollcycle import urlpatterns as _payrollprocessing_payrollcycle
from .PayrollProcessing.Payslip import urlpatterns as _payrollprocessing_payslip
from .AttendanceManagement.Shift import urlpatterns as _attendancemanagement_shift
from .AttendanceManagement.Shiftassignment import urlpatterns as _attendancemanagement_shiftassignment
from .AttendanceManagement.Record import urlpatterns as _attendancemanagement_record
from .AttendanceManagement.Geofence import urlpatterns as _attendancemanagement_geofence
from .AttendanceManagement.Regularization import urlpatterns as _attendancemanagement_regularization
from .EmployeeOnboarding.Template import urlpatterns as _employeeonboarding_template
from .EmployeeOnboarding.Templatetask import urlpatterns as _employeeonboarding_templatetask
from .EmployeeOnboarding.Program import urlpatterns as _employeeonboarding_program
from .EmployeeOnboarding.Task import urlpatterns as _employeeonboarding_task
from .EmployeeOnboarding.Document import urlpatterns as _employeeonboarding_document
from .EmployeeOnboarding.Assetallocation import urlpatterns as _employeeonboarding_assetallocation
from .EmployeeOnboarding.Orientationsession import urlpatterns as _employeeonboarding_orientationsession
from .EmployeeOffboarding.Separationcase import urlpatterns as _employeeoffboarding_separationcase
from .EmployeeOffboarding.RelievingLetter import urlpatterns as _employeeoffboarding_relievingletter
from .EmployeeOffboarding.ExperienceLetter import urlpatterns as _employeeoffboarding_experienceletter
from .EmployeeOffboarding.Letters import urlpatterns as _employeeoffboarding_letters
from .EmployeeOffboarding.Exitinterview import urlpatterns as _employeeoffboarding_exitinterview
from .EmployeeOffboarding.Clearanceitem import urlpatterns as _employeeoffboarding_clearanceitem
from .EmployeeOffboarding.Finalsettlement import urlpatterns as _employeeoffboarding_finalsettlement
from .JobRequisition.Jobdescriptiontemplate import urlpatterns as _jobrequisition_jobdescriptiontemplate
from .JobRequisition.Jobrequisition import urlpatterns as _jobrequisition_jobrequisition
from .JobRequisition.Approvals import urlpatterns as _jobrequisition_approvals
from .CandidateManagement.Candidate import urlpatterns as _candidatemanagement_candidate
from .CandidateManagement.Application import urlpatterns as _candidatemanagement_application
from .CandidateManagement.Tag import urlpatterns as _candidatemanagement_tag
from .CandidateManagement.Emailtemplate import urlpatterns as _candidatemanagement_emailtemplate
from .CandidateManagement.Communication import urlpatterns as _candidatemanagement_communication
from .CandidateManagement.CareersList import urlpatterns as _candidatemanagement_careerslist
from .CandidateManagement.CareersApply import urlpatterns as _candidatemanagement_careersapply
from .InterviewProcess.Interview import urlpatterns as _interviewprocess_interview
from .InterviewProcess.Interviewfeedback import urlpatterns as _interviewprocess_interviewfeedback
from .InterviewProcess.Feedbackcriterions import urlpatterns as _interviewprocess_feedbackcriterions
from .OfferManagement.Offerlettertemplate import urlpatterns as _offermanagement_offerlettertemplate
from .OfferManagement.Offer import urlpatterns as _offermanagement_offer
from .OfferManagement.OfferLetter import urlpatterns as _offermanagement_offerletter
from .OfferManagement.Offerapprovals import urlpatterns as _offermanagement_offerapprovals
from .OfferManagement.Preboardingitems import urlpatterns as _offermanagement_preboardingitems
from .OfferManagement.Backgroundverification import urlpatterns as _offermanagement_backgroundverification
from .StatutoryCompliance.Statutoryconfig import urlpatterns as _statutorycompliance_statutoryconfig
from .StatutoryCompliance.Statutorystaterule import urlpatterns as _statutorycompliance_statutorystaterule
from .StatutoryCompliance.Employeestatutoryidentifier import urlpatterns as _statutorycompliance_employeestatutoryidentifier
from .StatutoryCompliance.Statutoryreturn import urlpatterns as _statutorycompliance_statutoryreturn
from .StatutoryCompliance.ComplianceCalendar import urlpatterns as _statutorycompliance_compliancecalendar
from .TaxInvestment.Taxregimeconfig import urlpatterns as _taxinvestment_taxregimeconfig
from .TaxInvestment.RegimeComparison import urlpatterns as _taxinvestment_regimecomparison
from .TaxInvestment.Investmentdeclaration import urlpatterns as _taxinvestment_investmentdeclaration
from .TaxInvestment.Investmentproof import urlpatterns as _taxinvestment_investmentproof
from .TaxInvestment.Taxcomputation import urlpatterns as _taxinvestment_taxcomputation
from .TaxInvestment.Form16Partb import urlpatterns as _taxinvestment_form16partb
from .PayoutReports.Payoutbatch import urlpatterns as _payoutreports_payoutbatch
from .PayoutReports.PaymentRegister import urlpatterns as _payoutreports_paymentregister
from .PayoutReports.Payoutpayments import urlpatterns as _payoutreports_payoutpayments
from .PayoutReports.Exceptions import urlpatterns as _payoutreports_exceptions
from .PayoutReports.Payslipdistribution import urlpatterns as _payoutreports_payslipdistribution
from .PayoutReports.Bankreconciliation import urlpatterns as _payoutreports_bankreconciliation
from .GoalSetting.Goalperiod import urlpatterns as _goalsetting_goalperiod
from .GoalSetting.Objective import urlpatterns as _goalsetting_objective
from .GoalSetting.Keyresult import urlpatterns as _goalsetting_keyresult
from .GoalSetting.Goalcheckin import urlpatterns as _goalsetting_goalcheckin
from .PerformanceReview.Reviewcycle import urlpatterns as _performancereview_reviewcycle
from .PerformanceReview.Reviewtemplate import urlpatterns as _performancereview_reviewtemplate
from .PerformanceReview.Performancereview import urlpatterns as _performancereview_performancereview
from .PerformanceReview.Reviewrating import urlpatterns as _performancereview_reviewrating
from .PerformanceReview.CalibrationBoard import urlpatterns as _performancereview_calibrationboard
from .ContinuousFeedback.Kudosbadge import urlpatterns as _continuousfeedback_kudosbadge
from .ContinuousFeedback.Feedback import urlpatterns as _continuousfeedback_feedback
from .ContinuousFeedback.FeedbackDashboard import urlpatterns as _continuousfeedback_feedbackdashboard
from .ContinuousFeedback.Oneononemeeting import urlpatterns as _continuousfeedback_oneononemeeting
from .ContinuousFeedback.Meetingactionitem import urlpatterns as _continuousfeedback_meetingactionitem
from .PerformanceImprovement.Pip import urlpatterns as _performanceimprovement_pip
from .PerformanceImprovement.Pipcheckin import urlpatterns as _performanceimprovement_pipcheckin
from .PerformanceImprovement.Warningletter import urlpatterns as _performanceimprovement_warningletter
from .PerformanceImprovement.Coachingnote import urlpatterns as _performanceimprovement_coachingnote
from .TrainingManagement.Trainingcourse import urlpatterns as _trainingmanagement_trainingcourse
from .TrainingManagement.Trainingsession import urlpatterns as _trainingmanagement_trainingsession
from .TrainingManagement.Calendar import urlpatterns as _trainingmanagement_calendar
from .LearningManagement.Learningcontentitem import urlpatterns as _learningmanagement_learningcontentitem
from .LearningManagement.Learningpath import urlpatterns as _learningmanagement_learningpath
from .LearningManagement.Learningpathitem import urlpatterns as _learningmanagement_learningpathitem
from .LearningManagement.Learningprogress import urlpatterns as _learningmanagement_learningprogress
from .LearningManagement.Leaderboard import urlpatterns as _learningmanagement_leaderboard
from .LearningManagement.TeamProgress import urlpatterns as _learningmanagement_teamprogress
from .TrainingAdministration.Trainingnomination import urlpatterns as _trainingadministration_trainingnomination
from .TrainingAdministration.Trainingattendance import urlpatterns as _trainingadministration_trainingattendance
from .TrainingAdministration.Trainingfeedback import urlpatterns as _trainingadministration_trainingfeedback
from .TrainingAdministration.Trainingcertificate import urlpatterns as _trainingadministration_trainingcertificate
from .TrainingAdministration.Budget import urlpatterns as _trainingadministration_budget
from .PersonalInformation.MyInfo import urlpatterns as _personalinformation_myinfo
from .PersonalInformation.MyInfoEdit import urlpatterns as _personalinformation_myinfoedit
from .PersonalInformation.Emergencycontact import urlpatterns as _personalinformation_emergencycontact
from .PersonalInformation.Employeebankaccount import urlpatterns as _personalinformation_employeebankaccount
from .PersonalInformation.Familymember import urlpatterns as _personalinformation_familymember
from .PersonalInformation.Changerequest import urlpatterns as _personalinformation_changerequest
from .RequestManagement.MyRequests import urlpatterns as _requestmanagement_myrequests
from .RequestManagement.Documentrequest import urlpatterns as _requestmanagement_documentrequest
from .RequestManagement.Idcardrequest import urlpatterns as _requestmanagement_idcardrequest
from .RequestManagement.Assetrequest import urlpatterns as _requestmanagement_assetrequest
from .CommunicationHub.Celebrations import urlpatterns as _communicationhub_celebrations
from .CommunicationHub.Announcement import urlpatterns as _communicationhub_announcement
from .CommunicationHub.Survey import urlpatterns as _communicationhub_survey
from .CommunicationHub.Suggestion import urlpatterns as _communicationhub_suggestion
from .RequestManagement.Suggestions import urlpatterns as _requestmanagement_suggestions
from .HRReports.HrIndex import urlpatterns as _hrreports_hrindex
from .HRReports.Headcount import urlpatterns as _hrreports_headcount
from .HRReports.Attrition import urlpatterns as _hrreports_attrition
from .HRReports.Diversity import urlpatterns as _hrreports_diversity
from .HRReports.Cost import urlpatterns as _hrreports_cost
from .HRReports.Hiring import urlpatterns as _hrreports_hiring
from .AttendanceReports.AttendanceIndex import urlpatterns as _attendancereports_attendanceindex
from .AttendanceReports.AttendanceSummary import urlpatterns as _attendancereports_attendancesummary
from .AttendanceReports.LateEarly import urlpatterns as _attendancereports_lateearly
from .AttendanceReports.Absenteeism import urlpatterns as _attendancereports_absenteeism
from .AttendanceReports.Overtime import urlpatterns as _attendancereports_overtime
from .LeaveReports.LeaveIndex import urlpatterns as _leavereports_leaveindex
from .LeaveReports.LeaveRegister import urlpatterns as _leavereports_leaveregister
from .LeaveReports.LeaveLiability import urlpatterns as _leavereports_leaveliability
from .LeaveReports.CompOff import urlpatterns as _leavereports_compoff
from .LeaveReports.LeaveTrend import urlpatterns as _leavereports_leavetrend
from .PayrollReports.PayrollIndex import urlpatterns as _payrollreports_payrollindex
from .PayrollReports.SalaryRegister import urlpatterns as _payrollreports_salaryregister
from .PayrollReports.Tax import urlpatterns as _payrollreports_tax
from .PayrollReports.Statutory import urlpatterns as _payrollreports_statutory
from .PayrollReports.Ctc import urlpatterns as _payrollreports_ctc
from .PayrollReports.CostCenter import urlpatterns as _payrollreports_costcenter
from .AnalyticsDashboard.Executive import urlpatterns as _analyticsdashboard_executive
from .AnalyticsDashboard.Predictive import urlpatterns as _analyticsdashboard_predictive
from .AnalyticsDashboard.Benchmarking import urlpatterns as _analyticsdashboard_benchmarking
from .AnalyticsDashboard.Dashboard import urlpatterns as _analyticsdashboard_dashboard
from .AnalyticsDashboard.Widget import urlpatterns as _analyticsdashboard_widget
from .AssetManagement.Asset import urlpatterns as _assetmanagement_asset
from .AssetManagement.Assetmaintenance import urlpatterns as _assetmanagement_assetmaintenance
from .ExpenseManagement.Expensecategory import urlpatterns as _expensemanagement_expensecategory
from .ExpenseManagement.Expenseclaim import urlpatterns as _expensemanagement_expenseclaim
from .ExpenseManagement.Expenseclaimline import urlpatterns as _expensemanagement_expenseclaimline
from .TravelManagement.Travelpolicy import urlpatterns as _travelmanagement_travelpolicy
from .TravelManagement.Travelrequest import urlpatterns as _travelmanagement_travelrequest
from .TravelManagement.Travelbooking import urlpatterns as _travelmanagement_travelbooking
from .Helpdesk.Helpdeskslapolicy import urlpatterns as _helpdesk_helpdeskslapolicy
from .Helpdesk.Helpdeskcategory import urlpatterns as _helpdesk_helpdeskcategory
from .Helpdesk.Helpdeskticket import urlpatterns as _helpdesk_helpdeskticket
from .Helpdesk.Knowledgearticle import urlpatterns as _helpdesk_knowledgearticle
from .CompensationBenefits.Salarybenchmark import urlpatterns as _compensationbenefits_salarybenchmark
from .CompensationBenefits.Benefitplan import urlpatterns as _compensationbenefits_benefitplan
from .CompensationBenefits.Employeebenefitenrollment import urlpatterns as _compensationbenefits_employeebenefitenrollment
from .CompensationBenefits.Equitygrant import urlpatterns as _compensationbenefits_equitygrant
from .TalentManagement.Talentpool import urlpatterns as _talentmanagement_talentpool
from .TalentManagement.Talentpoolmembership import urlpatterns as _talentmanagement_talentpoolmembership
from .TalentManagement.NineBox import urlpatterns as _talentmanagement_ninebox
from .TalentManagement.Successionplan import urlpatterns as _talentmanagement_successionplan
from .TalentManagement.Successioncandidate import urlpatterns as _talentmanagement_successioncandidate
from .ComplianceLegal.Employmentcontract import urlpatterns as _compliancelegal_employmentcontract
from .ComplianceLegal.Hrpolicy import urlpatterns as _compliancelegal_hrpolicy
from .ComplianceLegal.Policyacknowledgment import urlpatterns as _compliancelegal_policyacknowledgment
from .ComplianceLegal.Grievance import urlpatterns as _compliancelegal_grievance
from .ComplianceLegal.Complianceregister import urlpatterns as _compliancelegal_complianceregister
from .WorkforcePlanning.GapAnalysis import urlpatterns as _workforceplanning_gapanalysis
from .WorkforcePlanning.Analytics import urlpatterns as _workforceplanning_analytics
from .WorkforcePlanning.Workforceplan import urlpatterns as _workforceplanning_workforceplan
from .WorkforcePlanning.Workforceplanline import urlpatterns as _workforceplanning_workforceplanline
from .WorkforcePlanning.Workforcescenario import urlpatterns as _workforceplanning_workforcescenario
from .WorkforcePlanning.Employeeskill import urlpatterns as _workforceplanning_employeeskill
from .EmployeeEngagement.Surveyactionplan import urlpatterns as _employeeengagement_surveyactionplan
from .EmployeeEngagement.Wellbeingprogram import urlpatterns as _employeeengagement_wellbeingprogram
from .EmployeeEngagement.Wellbeingparticipation import urlpatterns as _employeeengagement_wellbeingparticipation
from .EmployeeEngagement.Flexibleworkarrangement import urlpatterns as _employeeengagement_flexibleworkarrangement

app_name = "hrm"

urlpatterns = [
    *_employeemanagement_hrmoverview,  # EmployeeManagement/HrmOverview
    *_organizationalstructure_designation,  # OrganizationalStructure/Designation
    *_organizationalstructure_jobgrade,  # OrganizationalStructure/Jobgrade
    *_organizationalstructure_department,  # OrganizationalStructure/Department
    *_organizationalstructure_costcenter,  # OrganizationalStructure/Costcenter
    *_organizationalstructure_orgchart,  # OrganizationalStructure/OrgChart
    *_organizationalstructure_companysetup,  # OrganizationalStructure/CompanySetup
    *_employeemanagement_list,  # EmployeeManagement/List
    *_employeemanagement_form,  # EmployeeManagement/Form
    *_employeemanagement_detail,  # EmployeeManagement/Detail
    *_employeemanagement_document,  # EmployeeManagement/Document
    *_employeemanagement_lifecycle,  # EmployeeManagement/Lifecycle
    *_leavemanagement_type,  # LeaveManagement/Type
    *_leavemanagement_allocation,  # LeaveManagement/Allocation
    *_leavemanagement_request,  # LeaveManagement/Request
    *_leavemanagement_encashment,  # LeaveManagement/Encashment
    *_leavemanagement_policy,  # LeaveManagement/Policy
    *_timetracking_timesheet,  # TimeTracking/Timesheet
    *_timetracking_timesheetentry,  # TimeTracking/Timesheetentry
    *_timetracking_overtimerequest,  # TimeTracking/Overtimerequest
    *_timetracking_utilizationreport,  # TimeTracking/UtilizationReport
    *_timetracking_projecttimereport,  # TimeTracking/ProjectTimeReport
    *_holidaymanagement_publicholiday,  # HolidayManagement/Publicholiday
    *_holidaymanagement_holidaypolicy,  # HolidayManagement/Holidaypolicy
    *_holidaymanagement_floatingholidayelection,  # HolidayManagement/Floatingholidayelection
    *_salarystructure_paycomponent,  # SalaryStructure/Paycomponent
    *_salarystructure_salarystructuretemplate,  # SalaryStructure/Salarystructuretemplate
    *_salarystructure_employeesalarystructure,  # SalaryStructure/Employeesalarystructure
    *_payrollprocessing_payrollcycle,  # PayrollProcessing/Payrollcycle
    *_payrollprocessing_payslip,  # PayrollProcessing/Payslip
    *_attendancemanagement_shift,  # AttendanceManagement/Shift
    *_attendancemanagement_shiftassignment,  # AttendanceManagement/Shiftassignment
    *_attendancemanagement_record,  # AttendanceManagement/Record
    *_attendancemanagement_geofence,  # AttendanceManagement/Geofence
    *_attendancemanagement_regularization,  # AttendanceManagement/Regularization
    *_employeeonboarding_template,  # EmployeeOnboarding/Template
    *_employeeonboarding_templatetask,  # EmployeeOnboarding/Templatetask
    *_employeeonboarding_program,  # EmployeeOnboarding/Program
    *_employeeonboarding_task,  # EmployeeOnboarding/Task
    *_employeeonboarding_document,  # EmployeeOnboarding/Document
    *_employeeonboarding_assetallocation,  # EmployeeOnboarding/Assetallocation
    *_employeeonboarding_orientationsession,  # EmployeeOnboarding/Orientationsession
    *_employeeoffboarding_separationcase,  # EmployeeOffboarding/Separationcase
    *_employeeoffboarding_relievingletter,  # EmployeeOffboarding/RelievingLetter
    *_employeeoffboarding_experienceletter,  # EmployeeOffboarding/ExperienceLetter
    *_employeeoffboarding_letters,  # EmployeeOffboarding/Letters
    *_employeeoffboarding_exitinterview,  # EmployeeOffboarding/Exitinterview
    *_employeeoffboarding_clearanceitem,  # EmployeeOffboarding/Clearanceitem
    *_employeeoffboarding_finalsettlement,  # EmployeeOffboarding/Finalsettlement
    *_jobrequisition_jobdescriptiontemplate,  # JobRequisition/Jobdescriptiontemplate
    *_jobrequisition_jobrequisition,  # JobRequisition/Jobrequisition
    *_jobrequisition_approvals,  # JobRequisition/Approvals
    *_candidatemanagement_candidate,  # CandidateManagement/Candidate
    *_candidatemanagement_application,  # CandidateManagement/Application
    *_candidatemanagement_tag,  # CandidateManagement/Tag
    *_candidatemanagement_emailtemplate,  # CandidateManagement/Emailtemplate
    *_candidatemanagement_communication,  # CandidateManagement/Communication
    *_candidatemanagement_careerslist,  # CandidateManagement/CareersList
    *_candidatemanagement_careersapply,  # CandidateManagement/CareersApply
    *_interviewprocess_interview,  # InterviewProcess/Interview
    *_interviewprocess_interviewfeedback,  # InterviewProcess/Interviewfeedback
    *_interviewprocess_feedbackcriterions,  # InterviewProcess/Feedbackcriterions
    *_offermanagement_offerlettertemplate,  # OfferManagement/Offerlettertemplate
    *_offermanagement_offer,  # OfferManagement/Offer
    *_offermanagement_offerletter,  # OfferManagement/OfferLetter
    *_offermanagement_offerapprovals,  # OfferManagement/Offerapprovals
    *_offermanagement_preboardingitems,  # OfferManagement/Preboardingitems
    *_offermanagement_backgroundverification,  # OfferManagement/Backgroundverification
    *_statutorycompliance_statutoryconfig,  # StatutoryCompliance/Statutoryconfig
    *_statutorycompliance_statutorystaterule,  # StatutoryCompliance/Statutorystaterule
    *_statutorycompliance_employeestatutoryidentifier,  # StatutoryCompliance/Employeestatutoryidentifier
    *_statutorycompliance_statutoryreturn,  # StatutoryCompliance/Statutoryreturn
    *_statutorycompliance_compliancecalendar,  # StatutoryCompliance/ComplianceCalendar
    *_taxinvestment_taxregimeconfig,  # TaxInvestment/Taxregimeconfig
    *_taxinvestment_regimecomparison,  # TaxInvestment/RegimeComparison
    *_taxinvestment_investmentdeclaration,  # TaxInvestment/Investmentdeclaration
    *_taxinvestment_investmentproof,  # TaxInvestment/Investmentproof
    *_taxinvestment_taxcomputation,  # TaxInvestment/Taxcomputation
    *_taxinvestment_form16partb,  # TaxInvestment/Form16Partb
    *_payoutreports_payoutbatch,  # PayoutReports/Payoutbatch
    *_payoutreports_paymentregister,  # PayoutReports/PaymentRegister
    *_payoutreports_payoutpayments,  # PayoutReports/Payoutpayments
    *_payoutreports_exceptions,  # PayoutReports/Exceptions
    *_payoutreports_payslipdistribution,  # PayoutReports/Payslipdistribution
    *_payoutreports_bankreconciliation,  # PayoutReports/Bankreconciliation
    *_goalsetting_goalperiod,  # GoalSetting/Goalperiod
    *_goalsetting_objective,  # GoalSetting/Objective
    *_goalsetting_keyresult,  # GoalSetting/Keyresult
    *_goalsetting_goalcheckin,  # GoalSetting/Goalcheckin
    *_performancereview_reviewcycle,  # PerformanceReview/Reviewcycle
    *_performancereview_reviewtemplate,  # PerformanceReview/Reviewtemplate
    *_performancereview_performancereview,  # PerformanceReview/Performancereview
    *_performancereview_reviewrating,  # PerformanceReview/Reviewrating
    *_performancereview_calibrationboard,  # PerformanceReview/CalibrationBoard
    *_continuousfeedback_kudosbadge,  # ContinuousFeedback/Kudosbadge
    *_continuousfeedback_feedback,  # ContinuousFeedback/Feedback
    *_continuousfeedback_feedbackdashboard,  # ContinuousFeedback/FeedbackDashboard
    *_continuousfeedback_oneononemeeting,  # ContinuousFeedback/Oneononemeeting
    *_continuousfeedback_meetingactionitem,  # ContinuousFeedback/Meetingactionitem
    *_performanceimprovement_pip,  # PerformanceImprovement/Pip
    *_performanceimprovement_pipcheckin,  # PerformanceImprovement/Pipcheckin
    *_performanceimprovement_warningletter,  # PerformanceImprovement/Warningletter
    *_performanceimprovement_coachingnote,  # PerformanceImprovement/Coachingnote
    *_trainingmanagement_trainingcourse,  # TrainingManagement/Trainingcourse
    *_trainingmanagement_trainingsession,  # TrainingManagement/Trainingsession
    *_trainingmanagement_calendar,  # TrainingManagement/Calendar
    *_learningmanagement_learningcontentitem,  # LearningManagement/Learningcontentitem
    *_learningmanagement_learningpath,  # LearningManagement/Learningpath
    *_learningmanagement_learningpathitem,  # LearningManagement/Learningpathitem
    *_learningmanagement_learningprogress,  # LearningManagement/Learningprogress
    *_learningmanagement_leaderboard,  # LearningManagement/Leaderboard
    *_learningmanagement_teamprogress,  # LearningManagement/TeamProgress
    *_trainingadministration_trainingnomination,  # TrainingAdministration/Trainingnomination
    *_trainingadministration_trainingattendance,  # TrainingAdministration/Trainingattendance
    *_trainingadministration_trainingfeedback,  # TrainingAdministration/Trainingfeedback
    *_trainingadministration_trainingcertificate,  # TrainingAdministration/Trainingcertificate
    *_trainingadministration_budget,  # TrainingAdministration/Budget
    *_personalinformation_myinfo,  # PersonalInformation/MyInfo
    *_personalinformation_myinfoedit,  # PersonalInformation/MyInfoEdit
    *_personalinformation_emergencycontact,  # PersonalInformation/Emergencycontact
    *_personalinformation_employeebankaccount,  # PersonalInformation/Employeebankaccount
    *_personalinformation_familymember,  # PersonalInformation/Familymember
    *_personalinformation_changerequest,  # PersonalInformation/Changerequest
    *_requestmanagement_myrequests,  # RequestManagement/MyRequests
    *_requestmanagement_documentrequest,  # RequestManagement/Documentrequest
    *_requestmanagement_idcardrequest,  # RequestManagement/Idcardrequest
    *_requestmanagement_assetrequest,  # RequestManagement/Assetrequest
    *_communicationhub_celebrations,  # CommunicationHub/Celebrations
    *_communicationhub_announcement,  # CommunicationHub/Announcement
    *_communicationhub_survey,  # CommunicationHub/Survey
    *_communicationhub_suggestion,  # CommunicationHub/Suggestion
    *_requestmanagement_suggestions,  # RequestManagement/Suggestions
    *_hrreports_hrindex,  # HRReports/HrIndex
    *_hrreports_headcount,  # HRReports/Headcount
    *_hrreports_attrition,  # HRReports/Attrition
    *_hrreports_diversity,  # HRReports/Diversity
    *_hrreports_cost,  # HRReports/Cost
    *_hrreports_hiring,  # HRReports/Hiring
    *_attendancereports_attendanceindex,  # AttendanceReports/AttendanceIndex
    *_attendancereports_attendancesummary,  # AttendanceReports/AttendanceSummary
    *_attendancereports_lateearly,  # AttendanceReports/LateEarly
    *_attendancereports_absenteeism,  # AttendanceReports/Absenteeism
    *_attendancereports_overtime,  # AttendanceReports/Overtime
    *_leavereports_leaveindex,  # LeaveReports/LeaveIndex
    *_leavereports_leaveregister,  # LeaveReports/LeaveRegister
    *_leavereports_leaveliability,  # LeaveReports/LeaveLiability
    *_leavereports_compoff,  # LeaveReports/CompOff
    *_leavereports_leavetrend,  # LeaveReports/LeaveTrend
    *_payrollreports_payrollindex,  # PayrollReports/PayrollIndex
    *_payrollreports_salaryregister,  # PayrollReports/SalaryRegister
    *_payrollreports_tax,  # PayrollReports/Tax
    *_payrollreports_statutory,  # PayrollReports/Statutory
    *_payrollreports_ctc,  # PayrollReports/Ctc
    *_payrollreports_costcenter,  # PayrollReports/CostCenter
    *_analyticsdashboard_executive,  # AnalyticsDashboard/Executive
    *_analyticsdashboard_predictive,  # AnalyticsDashboard/Predictive
    *_analyticsdashboard_benchmarking,  # AnalyticsDashboard/Benchmarking
    *_analyticsdashboard_dashboard,  # AnalyticsDashboard/Dashboard
    *_analyticsdashboard_widget,  # AnalyticsDashboard/Widget
    *_assetmanagement_asset,  # AssetManagement/Asset
    *_assetmanagement_assetmaintenance,  # AssetManagement/Assetmaintenance
    *_expensemanagement_expensecategory,  # ExpenseManagement/Expensecategory
    *_expensemanagement_expenseclaim,  # ExpenseManagement/Expenseclaim
    *_expensemanagement_expenseclaimline,  # ExpenseManagement/Expenseclaimline
    *_travelmanagement_travelpolicy,  # TravelManagement/Travelpolicy
    *_travelmanagement_travelrequest,  # TravelManagement/Travelrequest
    *_travelmanagement_travelbooking,  # TravelManagement/Travelbooking
    *_helpdesk_helpdeskslapolicy,  # Helpdesk/Helpdeskslapolicy
    *_helpdesk_helpdeskcategory,  # Helpdesk/Helpdeskcategory
    *_helpdesk_helpdeskticket,  # Helpdesk/Helpdeskticket
    *_helpdesk_knowledgearticle,  # Helpdesk/Knowledgearticle
    *_compensationbenefits_salarybenchmark,  # CompensationBenefits/Salarybenchmark
    *_compensationbenefits_benefitplan,  # CompensationBenefits/Benefitplan
    *_compensationbenefits_employeebenefitenrollment,  # CompensationBenefits/Employeebenefitenrollment
    *_compensationbenefits_equitygrant,  # CompensationBenefits/Equitygrant
    *_talentmanagement_talentpool,  # TalentManagement/Talentpool
    *_talentmanagement_talentpoolmembership,  # TalentManagement/Talentpoolmembership
    *_talentmanagement_ninebox,  # TalentManagement/NineBox
    *_talentmanagement_successionplan,  # TalentManagement/Successionplan
    *_talentmanagement_successioncandidate,  # TalentManagement/Successioncandidate
    *_compliancelegal_employmentcontract,  # ComplianceLegal/Employmentcontract
    *_compliancelegal_hrpolicy,  # ComplianceLegal/Hrpolicy
    *_compliancelegal_policyacknowledgment,  # ComplianceLegal/Policyacknowledgment
    *_compliancelegal_grievance,  # ComplianceLegal/Grievance
    *_compliancelegal_complianceregister,  # ComplianceLegal/Complianceregister
    *_workforceplanning_gapanalysis,  # WorkforcePlanning/GapAnalysis
    *_workforceplanning_analytics,  # WorkforcePlanning/Analytics
    *_workforceplanning_workforceplan,  # WorkforcePlanning/Workforceplan
    *_workforceplanning_workforceplanline,  # WorkforcePlanning/Workforceplanline
    *_workforceplanning_workforcescenario,  # WorkforcePlanning/Workforcescenario
    *_workforceplanning_employeeskill,  # WorkforcePlanning/Employeeskill
    *_employeeengagement_surveyactionplan,  # EmployeeEngagement/Surveyactionplan
    *_employeeengagement_wellbeingprogram,  # EmployeeEngagement/Wellbeingprogram
    *_employeeengagement_wellbeingparticipation,  # EmployeeEngagement/Wellbeingparticipation
    *_employeeengagement_flexibleworkarrangement,  # EmployeeEngagement/Flexibleworkarrangement
]
