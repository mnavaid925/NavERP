# Gap Register: eCommerce 9.4 Shopping Cart & Checkout

## Overview
Sub-Module 9.4 covers Shopping Carts & Guest Sessions, Abandoned Cart Recovery, One-Page & Multi-Step Checkout Funnels, Shipping Method Calculation Matrices, and Payment Gateway Configuration.

## Register

| ID | Title | Owner | Blocked On / Prerequisite | Status | Done When |
|---|---|---|---|---|---|
| GAP-ECOM-9.4-01 | Webhook / Gateway Live Payment Capture Transport | apps.ecommerce / 9.5 OMS | Upstream payment gateway merchant credentials & live provider API endpoints | `- [~]` Deferred | Sub-Module 9.5 Order Management System (OMS) implements live external capture callbacks |
| GAP-ECOM-9.4-02 | Background Email Worker for Cart Abandonment | apps.ecommerce | Shared Background Task Worker (Celery / cron automation) | `- [~]` Deferred | Cron / Celery automation fires periodic `mark_abandoned()` and dispatches recovery emails |

## Closed Items
All planned 9.4 scope, entities, routes, templates, admin registrations, idempotent seeders, navigation items, review findings, and test suites are 100% complete and verified green with 0 remaining defects.
