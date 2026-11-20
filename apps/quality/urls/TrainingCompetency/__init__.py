from apps.quality.urls.TrainingCompetency.CompetencyCertifications import urlpatterns as cert_patterns
from apps.quality.urls.TrainingCompetency.CompetencyMatrices import urlpatterns as matrix_patterns
from apps.quality.urls.TrainingCompetency.QualityTrainingCourses import urlpatterns as course_patterns
from apps.quality.urls.TrainingCompetency.TrainingEnrollments import urlpatterns as enrollment_patterns

urlpatterns = [
    *matrix_patterns,
    *course_patterns,
    *enrollment_patterns,
    *cert_patterns,
]
