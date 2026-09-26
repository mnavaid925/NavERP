from .CPQQuotes import urlpatterns as quote_patterns
from .CPQQuoteLines import urlpatterns as line_patterns
from .ProductBundles import urlpatterns as bundle_patterns
from .QuoteApprovalRules import urlpatterns as rule_patterns
from .QuoteOperations import urlpatterns as operation_patterns

urlpatterns = (
    operation_patterns +
    quote_patterns +
    line_patterns +
    bundle_patterns +
    rule_patterns
)
