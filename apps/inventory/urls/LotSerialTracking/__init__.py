from .FefoBoard import urlpatterns as _lst_fefo
from .LotNumberRules import urlpatterns as _lst_lotrules
from .ShelfLifePolicies import urlpatterns as _lst_policies
from .Traceability import urlpatterns as _lst_trace

urlpatterns = [
    *_lst_lotrules,
    *_lst_policies,
    *_lst_fefo,
    *_lst_trace,
]
