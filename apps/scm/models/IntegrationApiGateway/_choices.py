"""SCM 4.19 Integration & API Gateway — the vocabularies shared across the sub-module.

**Ownership.** This file is written by the ``IntegrationEndpoints`` (entity 1) backend agent and by
nobody else. ``IntegrationMessages``, ``WebhookSubscriptions`` and ``WebhookDeliveries`` import from
it **by name** (``from apps.scm.models.IntegrationApiGateway._choices import ...``) and must never
create or edit it. One writer, three readers — which is the whole reason a shared vocabulary is a
file rather than four copies of a list.

**Why by name and never ``import *``.** ``apps/scm/models/__init__.py`` already star-imports several
``_choices`` modules, so a further star-import re-declaring a shared token would **silently shadow**
one of them, with the winner decided by import order. Spelling every name out makes such a collision
a visible edit instead of a runtime coin-flip. (Checked at write time: none of the names in
:data:`__all__` is declared anywhere else in ``apps/scm``.) The identical note sits at
``ThirdPartyLogistics/LogisticsClients.py:41-47``.

**Pure data — this module imports NOTHING**, not even ``_base``. The dependency edge inside 4.19
therefore only ever runs one way (the four entity modules -> ``_choices``) and no import cycle is
possible.

**No badge-CSS dicts here, deliberately.** 4.17's ``_choices.py`` carries ``*_CSS`` maps because its
badge colour is decided in one place and read from two pages. 4.19's frozen contract spells the badge
colours as ``{% if %}`` chains in the templates instead, so a CSS dict here would be a table nothing
imports. If a later pass wants one, it belongs here — and it may only use the six classes that exist
in ``static/css/theme.css``: ``badge-green`` / ``badge-red`` / ``badge-amber`` / ``badge-info`` /
``badge-muted`` / ``badge-slate``. There is no ``badge-success`` / ``badge-warning`` /
``badge-danger``; those render completely unstyled (L33, already shipped four times).
"""

__all__ = [
    # IntegrationEndpoint
    "ENDPOINT_CATEGORY_CHOICES",
    "ENDPOINT_SYSTEM_CHOICES",
    "ENDPOINT_DIRECTION_CHOICES",
    "TRANSPORT_CHOICES",
    "AUTH_METHOD_CHOICES",
    "TRIGGER_MODE_CHOICES",
    "ENVIRONMENT_CHOICES",
    "LIFECYCLE_STAGE_CHOICES",
    "ENDPOINT_STATUS_CHOICES",
    # IntegrationMessage
    "MESSAGE_DIRECTION_CHOICES",
    "DOCUMENT_TYPE_CHOICES",
    "MESSAGE_STATUS_CHOICES",
    "MESSAGE_SOURCE_CHOICES",
    # WebhookSubscription
    "WEBHOOK_ENTITY_CHOICES",
    "WEBHOOK_EVENT_CHOICES",
    "PAYLOAD_FORMAT_CHOICES",
    # WebhookDelivery
    "DELIVERY_STATUS_CHOICES",
    "DELIVERY_BACKOFF_SECONDS",
]


# =================================================================================================
# IntegrationEndpoint — one connection to one outside system
# =================================================================================================

#: The four NavERP.md 4.19 bullets that are really ONE table, plus the escape hatch. ``category`` is
#: the DISCRIMINATOR: "ERP Integration", "E-commerce Integration", "IoT Gateway" and "EDI Management"
#: are four sidebar bullets, four category-scoped routes and one model — the same compression
#: ``accounting.IntegrationConfig`` made with its own ``CATEGORY_CHOICES``. Four near-identical tables
#: would be four copies of the same credential, transport and lifecycle columns, and the copy that
#: gets missed on the next change is the one that keeps a stale rule.
#:
#: ``max_length=12`` against a 9-char longest value (``ecommerce``).
ENDPOINT_CATEGORY_CHOICES = [
    ("erp", "ERP"),
    ("ecommerce", "E-commerce"),
    ("iot", "IoT"),
    ("edi", "EDI"),
    ("custom", "Custom"),
]

#: WHICH system is on the other end. Free-text would make "SAP", "sap" and "S.A.P." three different
#: systems on a filter dropdown, so this is a closed list of the platforms the surveyed integration
#: layers actually ship connectors for — plus ``custom`` for everything else, which is an honest
#: answer rather than an empty one.
#:
#: ``max_length=20`` against a 15-char longest value (``barcode_scanner``).
ENDPOINT_SYSTEM_CHOICES = [
    ("sap", "SAP"),
    ("oracle", "Oracle"),
    ("netsuite", "NetSuite"),
    ("dynamics", "Microsoft Dynamics"),
    ("shopify", "Shopify"),
    ("magento", "Magento"),
    ("woocommerce", "WooCommerce"),
    ("amazon", "Amazon"),
    ("ebay", "eBay"),
    ("walmart", "Walmart"),
    ("rfid_reader", "RFID Reader"),
    ("barcode_scanner", "Barcode Scanner"),
    ("sensor_gateway", "Sensor Gateway"),
    ("edi_van", "EDI VAN"),
    ("custom", "Custom"),
]

#: Which way the data flows. ``bidirectional`` is the default because most ERP and marketplace
#: connectors are both — we push fulfilments and pull orders over the same registered connection.
#:
#: ``max_length=14`` against a 13-char longest value (``bidirectional``).
ENDPOINT_DIRECTION_CHOICES = [
    ("inbound", "Inbound"),
    ("outbound", "Outbound"),
    ("bidirectional", "Bidirectional"),
]

#: HOW the bytes move. The list is wider than HTTP on purpose: EDI still runs over ``as2`` and ``van``
#: and ``sftp``, and an RFID reader speaks ``llrp`` or ``serial``, not REST. This is exactly why
#: ``IntegrationEndpoint.endpoint_url`` is a ``CharField`` rather than a ``URLField`` — see the field
#: comment there before "fixing" it.
#:
#: ``max_length=12`` against a 9-char longest value (``file_drop``).
TRANSPORT_CHOICES = [
    ("api_rest", "REST API"),
    ("api_soap", "SOAP API"),
    ("webhook", "Webhook"),
    ("sftp", "SFTP"),
    ("ftps", "FTPS"),
    ("as2", "AS2"),
    ("van", "VAN"),
    ("file_drop", "File Drop"),
    ("mqtt", "MQTT"),
    ("llrp", "LLRP"),
    ("serial", "Serial"),
    ("manual", "Manual"),
]

#: How we would authenticate if 4.19 shipped transport, which it does not. ``oauth2`` RECORDS INTENT
#: and stores nothing: authorization-code flows and token storage are deferred out of scope, and a
#: token column that is always empty would read as a broken feature rather than an unbuilt one.
#:
#: ``max_length=10`` against two 7-char values (``api_key``, ``ssh_key``).
AUTH_METHOD_CHOICES = [
    ("none", "None"),
    ("api_key", "API Key"),
    ("basic", "Basic Auth"),
    ("oauth2", "OAuth 2.0"),
    ("mtls", "Mutual TLS"),
    ("ssh_key", "SSH Key"),
]

#: What WOULD start an exchange. Records intent only — **4.19 ships no scheduler and no daemon**, so
#: nothing polls, nothing fires and ``scheduled`` does not cause anything to happen. The same posture
#: 4.17 took with ``LogisticsClient.next_billing_date``.
#:
#: ``max_length=10`` against a 9-char longest value (``scheduled``).
TRIGGER_MODE_CHOICES = [
    ("realtime", "Real-time"),
    ("scheduled", "Scheduled"),
    ("manual", "Manual"),
]

#: Sandbox or production. Two values and no third: a "staging" that behaves like neither is how a
#: test order ends up in a live marketplace. Sandbox->production PROMOTION (cloning a configuration
#: between environments) is deferred out of scope — this column records which one a connection points
#: at, nothing more.
#:
#: ``max_length=10`` against a 10-char longest value (``production``).
ENVIRONMENT_CHOICES = [
    ("production", "Production"),
    ("sandbox", "Sandbox"),
]

#: How far along the onboarding of this connection is, which is a DIFFERENT question from whether it
#: is currently up (:data:`ENDPOINT_STATUS_CHOICES`). ``certified`` is the one that earns its place:
#: EDI trading partners run a certification cycle before go-live, and "tested but not yet certified"
#: is the state a partner spends weeks in.
#:
#: ``max_length=10`` against two 9-char values (``certified``, ``suspended``).
LIFECYCLE_STAGE_CHOICES = [
    ("setup", "Setup"),
    ("testing", "Testing"),
    ("certified", "Certified"),
    ("live", "Live"),
    ("suspended", "Suspended"),
]

#: The CURRENT health of the connection — deliberately the same four values
#: ``accounting.IntegrationConfig.STATUS_CHOICES`` uses, plus ``disabled``. It is a
#: human-maintained MARKER on the form, not workflow-owned state: 4.19 ships no transport, so nothing
#: can observe a connection succeed or fail and there is no state machine to own the column.
#:
#: ``max_length=14`` against a 12-char longest value (``disconnected``).
ENDPOINT_STATUS_CHOICES = [
    ("disconnected", "Disconnected"),
    ("connected", "Connected"),
    ("error", "Error"),
    ("disabled", "Disabled"),
]


# =================================================================================================
# IntegrationMessage — the append-only exchange log
# =================================================================================================

#: ``max_length=8`` against an 8-char longest value (``outbound``).
MESSAGE_DIRECTION_CHOICES = [
    ("inbound", "Inbound"),
    ("outbound", "Outbound"),
]

#: WHAT crossed the boundary. The X12 members are the thirteen transaction sets a supply-chain EDI
#: programme actually runs (850/855/860 for the order, 856 for the shipment, 810/820 for the money,
#: 846 for inventory, 214 for status, 864 for text, the 940/945/947 warehouse trio, and 997 to
#: acknowledge any of them); the non-EDI members are the marketplace, e-commerce and IoT payloads
#: that use the identical log. **Envelope PARSING is deferred** — nothing here reads an X12 file, and
#: 997 auto-generation is explicitly out of scope; this column records what a row IS, not what a
#: parser decided.
#:
#: ``max_length=20`` against a 17-char longest value (``fulfilment_export``).
DOCUMENT_TYPE_CHOICES = [
    ("edi_850", "850 Purchase Order"),
    ("edi_855", "855 PO Acknowledgement"),
    ("edi_860", "860 PO Change"),
    ("edi_856", "856 Advance Ship Notice"),
    ("edi_810", "810 Invoice"),
    ("edi_820", "820 Payment/Remittance"),
    ("edi_846", "846 Inventory Advice"),
    ("edi_214", "214 Shipment Status"),
    ("edi_864", "864 Text Message"),
    ("edi_940", "940 Warehouse Shipping Order"),
    ("edi_945", "945 Warehouse Shipping Advice"),
    ("edi_947", "947 Warehouse Inventory Adjustment"),
    ("edi_997", "997 Functional Acknowledgement"),
    ("order_import", "Order Import"),
    ("inventory_feed", "Inventory Feed"),
    ("fulfilment_export", "Fulfilment Export"),
    ("item_export", "Item Export"),
    ("refund_sync", "Refund Sync"),
    ("customer_sync", "Customer Sync"),
    ("tag_read_batch", "Tag Read Batch"),
    ("scan_batch", "Scan Batch"),
    ("sensor_reading", "Sensor Reading"),
    ("other", "Other"),
]

#: ``sent`` and ``received`` are kept apart from ``acknowledged`` because they are different facts: we
#: put it on the wire / it reached us, versus the partner confirmed it. On an EDI programme that
#: distinction IS the dispute — "we sent the 850" and "they acknowledged the 850" are what the two
#: sides argue about. ``ignored`` is a first-class answer for a duplicate or an out-of-scope payload,
#: so a deliberately-dropped message never sits in the exceptions cockpit as a failure.
#:
#: ``max_length=14`` against a 12-char longest value (``acknowledged``).
MESSAGE_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("sent", "Sent"),
    ("received", "Received"),
    ("acknowledged", "Acknowledged"),
    ("failed", "Failed"),
    ("ignored", "Ignored"),
]

#: The SOFT POINTER's vocabulary — which internal document this exchange is about. **scm bans
#: ``GenericForeignKey``** (``ColdChainMonitors.py:18``, ``PortalDocumentShares.py:9-11``: a
#: ``(content_type, object_id)`` pair cannot be tenant-joined), so correlation is this choice plus a
#: ``source_reference`` string — the ``DemandSignals.py:74`` /
#: ``ComplianceRequirements.py:239`` / ``ClientBillingRunLines.py:810`` idiom. Only the two flows
#: worth joining (``purchase_order``, ``sales_order``) additionally get a TYPED nullable FK;
#: everything else on this list is reachable through the string alone, on purpose.
#:
#: ``none`` is a real answer: an inventory feed or a sensor batch is about no single document.
#:
#: ``max_length=22`` against a 20-char longest value (``return_authorization``).
MESSAGE_SOURCE_CHOICES = [
    ("purchase_order", "Purchase Order"),
    ("goods_receipt", "Goods Receipt"),
    ("sales_order", "Sales Order"),
    ("shipment", "Shipment"),
    ("freight_invoice", "Freight Invoice"),
    ("stock_move", "Stock Move"),
    ("item", "Item"),
    ("trade_document", "Trade Document"),
    ("return_authorization", "Return Authorization"),
    ("logistics_client", "Logistics Client"),
    ("none", "None"),
]


# =================================================================================================
# WebhookSubscription — a rule about internal events
# =================================================================================================

#: WHAT can fire a webhook. **Every member is a verified existing scm class**, which is precisely why
#: this list exists rather than reusing ``crm.Webhook``: that model's entity vocabulary comes from
#: ``crm.WorkflowRule.ENTITY_CHOICES`` (``apps/crm/models/AutomationWorkflow/Webhooks.py:3,17``) and
#: is a CRM vocabulary — lead, opportunity, case — which cannot express ``shipment.delivered`` or
#: ``goods_receipt.posted``. A documented decision, not drift.
#:
#: ``max_length=22`` against a 20-char longest value (``return_authorization``).
WEBHOOK_ENTITY_CHOICES = [
    ("purchase_order", "Purchase Order"),
    ("goods_receipt", "Goods Receipt"),
    ("sales_order", "Sales Order"),
    ("shipment", "Shipment"),
    ("stock_move", "Stock Move"),
    ("return_authorization", "Return Authorization"),
    ("quality_inspection", "Quality Inspection"),
    ("work_order", "Work Order"),
    ("asset", "Asset"),
    ("supply_chain_alert", "Supply Chain Alert"),
]

#: WHICH change fires it. ``status_changed`` is separate from ``updated`` because a subscriber who
#: only cares that an order moved does not want a notification for every note somebody typed.
#:
#: ``max_length=16`` against a 14-char longest value (``status_changed``).
WEBHOOK_EVENT_CHOICES = [
    ("created", "Created"),
    ("updated", "Updated"),
    ("status_changed", "Status Changed"),
    ("approved", "Approved"),
    ("posted", "Posted"),
    ("cancelled", "Cancelled"),
    ("delivered", "Delivered"),
]

#: ``max_length=6`` against a 4-char longest value (``json``).
PAYLOAD_FORMAT_CHOICES = [
    ("json", "JSON"),
    ("xml", "XML"),
]


# =================================================================================================
# WebhookDelivery — one attempt at one subscription
# =================================================================================================

#: ``simulated`` is the honest member and it is what keeps this table from lying: 4.19 ships **no
#: outbound HTTP**, so a row that never left the process is neither a success nor a failure, and
#: recording it as ``success`` would make the delivery log evidence of something that did not happen.
#: ``exhausted`` is separate from ``failed`` because "this attempt failed" and "we have stopped
#: trying" are different operational facts and only one of them needs a human.
#:
#: ``max_length=10`` against two 9-char values (``exhausted``, ``simulated``).
DELIVERY_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("exhausted", "Exhausted"),
    ("simulated", "Simulated"),
]

#: Svix's published retry schedule: 8 attempts spread over roughly 32 hours (immediate, 5s, 5m, 30m,
#: 2h, 5h, 10h, 10h). Adopted verbatim rather than invented because a backoff curve is one of the few
#: things in webhook delivery with a de-facto industry answer, and a home-grown one is a number
#: nobody can reason about when a partner asks how long we keep trying.
#:
#: **MODEL THE STATE, NOT THE DAEMON.** There is no scheduler in this pass: a human presses Retry and
#: ``webhookdelivery_retry`` stamps ``next_attempt_at`` at the next slot in this tuple. Nothing runs
#: on a clock, and ``len()`` of this tuple is what the detail page renders as "attempt N of 8".
DELIVERY_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)
