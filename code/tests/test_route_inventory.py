"""
test_route_inventory.py

Safety net for the branch merges (audit-dashboard, feature/aas-integration):
every route that main serves must still be registered afterwards, with at least
the same HTTP methods.  Conflict resolution in app.py (routes moved into
create_app(), blueprints re-registered) can silently drop a route; this test
names the one that went missing.

New routes are allowed.  When a route is removed on purpose, delete its line
here in the same commit.
"""

import pytest

# Baseline: all routes of main after the demo stack was merged (#8, #9), plus each merged branch.
BASELINE_ROUTES = [
    ('/',                                   {'GET'}),
    ('/3d-view',                            {'GET'}),
    ('/IMPEMTemp-data',                     {'GET'}),
    ('/UpdateUser',                         {'POST'}),
    ('/api/colors',                         {'GET'}),
    ('/api/colors',                         {'POST'}),
    ('/api/colors/reset',                   {'POST'}),
    ('/api/dashboard',                      {'GET'}),
    ('/api/events/recent',                  {'GET'}),
    ('/api/get-all-topics',                 {'GET'}),
    ('/api/get-workflow',                   {'GET'}),
    ('/api/health',                         {'GET'}),
    ('/api/order-status',                   {'GET'}),
    ('/api/process-qbd-analysis',           {'GET'}),
    ('/api/released-orders',                {'GET'}),
    ('/api/running-order',                  {'GET'}),
    ('/api/topic/<topic>/events',           {'GET'}),
    ('/api/tree',                           {'GET'}),
    ('/api/workflows',                      {'POST'}),
    ('/batch',                              {'GET'}),
    ('/data-tree',                          {'GET'}),
    ('/data/<topic>',                       {'GET'}),
    ('/deactivate-workflow/<workflow_name>', {'POST'}),
    ('/delete-workflow/<workflow_name>',    {'POST'}),
    ('/design-space-definition',            {'GET'}),
    ('/design-space-representation',        {'GET'}),
    ('/equipment-overview',                 {'GET'}),
    ('/favicon.ico',                        {'GET'}),
    ('/get-all-workflows',                  {'GET'}),
    ('/get-latest-values',                  {'GET'}),
    ('/get-product-trend/<product>',        {'GET'}),
    ('/get-products',                       {'GET'}),
    ('/get-released-workflows',             {'GET'}),
    ('/get-role',                           {'POST'}),
    ('/get-set/<set_id>',                   {'GET'}),
    ('/get-sets',                           {'GET'}),
    ('/get-workflow/<workflow_name>',       {'GET'}),
    ('/get-workflows',                      {'GET'}),
    ('/index',                              {'GET'}),
    ('/initial-index',                      {'GET'}),
    ('/login-error',                        {'GET'}),
    ('/loginUser',                          {'POST'}),
    ('/logout-message',                     {'GET'}),
    ('/logoutUser',                         {'POST'}),
    ('/manufacturing-orders',               {'GET', 'POST'}),
    ('/manufacturing-orders-data',          {'GET', 'POST'}),
    ('/order-management',                   {'GET', 'POST'}),
    ('/orders',                             {'GET'}),
    ('/plantconfig',                        {'GET'}),
    ('/process-instructions',               {'GET'}),
    ('/process-qbd-analysis',               {'GET'}),
    ('/processconfig',                      {'GET'}),
    ('/product_analytics',                  {'GET'}),
    ('/registerUser',                       {'POST'}),
    ('/release-workflow/<workflow_name>',   {'POST'}),
    ('/role-management',                    {'GET'}),
    ('/sampling',                           {'GET'}),
    ('/save-plant-config',                  {'POST'}),
    ('/save-set',                           {'POST'}),
    ('/save-workflow',                      {'POST'}),
    ('/scada',                              {'GET'}),
    ('/settings',                           {'GET'}),
    ('/static/<path:filename>',             {'GET'}),
    ('/submit-order',                       {'POST'}),
    ('/subscription-management',            {'GET'}),
    ('/subscription-management',            {'POST'}),
    ('/update-role',                        {'POST'}),
    ('/updated-user',                       {'GET'}),
    ('/user-management',                    {'GET'}),
    ('/user-profile',                       {'GET'}),
    ('/workflow-management',                {'GET'}),
    ('/workflow-overview',                  {'GET'}),

    # audit-dashboard (merge step 3)
    ('/audit/',                             {'GET'}),
    ('/audit/api/stats',                    {'GET'}),
    ('/audit/api/logs',                     {'GET'}),
    ('/audit/api/integrity',                {'GET'}),
    ('/audit/api/logs/export',              {'GET'}),
    ('/audit/api/siem',                     {'GET'}),
]


def _registered_methods(app):
    """Map each URL rule to the union of methods registered for it (HEAD/OPTIONS ignored)."""
    methods = {}
    for rule in app.url_map.iter_rules():
        methods.setdefault(rule.rule, set()).update(rule.methods - {'HEAD', 'OPTIONS'})
    return methods


@pytest.mark.parametrize(
    'rule, methods', BASELINE_ROUTES,
    ids=[f"{' '.join(sorted(m))} {r}" for r, m in BASELINE_ROUTES],
)
def test_baseline_route_is_still_registered(app, rule, methods):
    registered = _registered_methods(app)
    assert rule in registered, f"route {rule} is no longer registered"
    missing = methods - registered[rule]
    assert not missing, f"route {rule} lost method(s) {sorted(missing)}"
