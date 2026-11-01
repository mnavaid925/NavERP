from apps.ecommerce.views.ContentManagement.CmsPages import (
    cmspage_create,
    cmspage_delete,
    cmspage_detail,
    cmspage_edit,
    cmspage_list,
    cmspage_preview,
)
from apps.ecommerce.views.ContentManagement.BlogArticles import (
    blogarticle_create,
    blogarticle_delete,
    blogarticle_detail,
    blogarticle_edit,
    blogarticle_list,
)
from apps.ecommerce.views.ContentManagement.MediaAssets import (
    mediaasset_create,
    mediaasset_delete,
    mediaasset_detail,
    mediaasset_edit,
    mediaasset_list,
)
from apps.ecommerce.views.ContentManagement.ContentBlocks import (
    contentblock_create,
    contentblock_delete,
    contentblock_detail,
    contentblock_edit,
    contentblock_list,
)

__all__ = [
    "cmspage_list",
    "cmspage_detail",
    "cmspage_create",
    "cmspage_edit",
    "cmspage_delete",
    "cmspage_preview",
    "blogarticle_list",
    "blogarticle_detail",
    "blogarticle_create",
    "blogarticle_edit",
    "blogarticle_delete",
    "mediaasset_list",
    "mediaasset_detail",
    "mediaasset_create",
    "mediaasset_edit",
    "mediaasset_delete",
    "contentblock_list",
    "contentblock_detail",
    "contentblock_create",
    "contentblock_edit",
    "contentblock_delete",
]
