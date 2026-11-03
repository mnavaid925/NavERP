# Gap Register: Sub-module 9.19 — Integration & API Ecosystem

**Module:** 9 eCommerce Management System (`ecommerce`)  
**Sub-module:** 9.19 Integration & API Ecosystem  
**Created:** 2026-11-03  
**Status:** Active  

---

### GAP-9.19-01: Third-Party Secret Storage Symmetric Envelope Encryption at Rest
- **Owner:** Security / DevSecOps / eCommerce Team
- **Waiting For / Blocked On:** Enterprise Key Management Service (KMS) or shared Fernet encryption infrastructure module landing across NavERP.
- **Status:** `- [ ]` Open / Deferred
- **Done When:** External credentials (`EcommerceConnector.api_secret` and `WebhookSubscription.secret_key`) are encrypted at rest using envelope encryption rather than raw cleartext `CharField` in the database.

### GAP-9.19-02: `ApiCredential` Foreign Key Integration with `core.Party` (`issued_to_party`)
- **Owner:** eCommerce / Core B2B Team
- **Waiting For / Blocked On:** Sub-module B2B wholesale portal / external developer portal customer login flows.
- **Status:** `- [ ]` Open / Deferred
- **Done When:** `ApiCredential` model is extended with `issued_to_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="ecommerce_api_credentials")` to link headless API tokens to wholesale buyers and partner accounts.
