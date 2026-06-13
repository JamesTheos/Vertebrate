"""
app_registry.py

Single source of truth for the set of subscribable application names.

Consumed by:
  - app.py  → /subscription-management (builds the admin toggle UI state)
  - createDB.py → _seed_subscriptions() (seeds each app as unsubscribed)

Keeping one list prevents the two from drifting.  They previously held separate
hard-coded copies, and the `aas` app was missing from both — which made the AAS
feature impossible to enable in a fresh deploy.  Add new subscribable apps here.

NOTE: the subscription-management template (subscription-management.html) renders
one checkbox per app keyed by these names (id="<app-name>"); add a matching
toggle there when adding an app.
"""

KNOWN_APPS = [
    'manufacturing-orders', 'order-management', 'workflow-overview',
    'batch', 'process-instructions', 'sampling', 'equipment', 'pid',
    '3d-view', 'design-space-definition', 'design-space-representation',
    'product-analytics', 'process-qbd-analytics', 'plant-configuration',
    'process-configuration', 'workflow-management', 'user-management',
    'role-management', 'aas',
]
