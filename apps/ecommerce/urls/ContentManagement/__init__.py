from apps.ecommerce.urls.ContentManagement.BlogArticles import (
    urlpatterns as blogarticles_patterns,
)
from apps.ecommerce.urls.ContentManagement.CmsPages import (
    urlpatterns as cmspages_patterns,
)
from apps.ecommerce.urls.ContentManagement.ContentBlocks import (
    urlpatterns as contentblocks_patterns,
)
from apps.ecommerce.urls.ContentManagement.MediaAssets import (
    urlpatterns as mediaassets_patterns,
)

urlpatterns = (
    cmspages_patterns
    + blogarticles_patterns
    + mediaassets_patterns
    + contentblocks_patterns
)
