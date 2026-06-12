"""
Configuration constants for 21 CFR Part 11 audit trail
Defines action types, record types, and field requirements
"""

# ============================================================================
# ACTION TYPES - What happened
# ============================================================================

# User actions
ACTION_LOGIN = 'LOGIN'
ACTION_LOGOUT = 'LOGOUT'
ACTION_LOGIN_FAILED = 'LOGIN_FAILED'

# CRUD operations
ACTION_CREATE = 'CREATE'
ACTION_UPDATE = 'UPDATE'
ACTION_DELETE = 'DELETE'
ACTION_VIEW = 'VIEW'

# System actions
ACTION_SYSTEM = 'SYSTEM'
ACTION_EXPORT = 'EXPORT'

# ============================================================================
# RECORD TYPES - What was affected
# ============================================================================

# User management
RECORD_USER = 'USER'
RECORD_ROLE = 'ROLE'
RECORD_PERMISSION = 'PERMISSION'
RECORD_PASSWORD = 'PASSWORD'

# Application entities
RECORD_SUBSCRIPTION = 'SUBSCRIPTION'
RECORD_WORKFLOW = 'WORKFLOW'
RECORD_ORDER = 'ORDER'

# Digital Twin / AAS
RECORD_AAS = 'AAS'

# System
RECORD_SYSTEM = 'SYSTEM'

# ============================================================================
# FIELD REQUIREMENTS - 21 CFR Part 11 Compliance
# ============================================================================

# Fields that REQUIRE a change_reason (sensitive operations)
REQUIRE_REASON_FIELDS = [
    'password',
    'role',
    'permissions',
    'subscribed'  # Subscription status changes
]

# Record types that ALWAYS require change_reason
REQUIRE_REASON_RECORDS = [
    RECORD_PASSWORD,
    RECORD_ROLE,
    RECORD_PERMISSION
]

# Actions that ALWAYS require change_reason
REQUIRE_REASON_ACTIONS = [
    ACTION_DELETE,
    #ACTION_UPDATE
]

# ============================================================================
# SECURITY - Fields to exclude from logging
# ============================================================================

# Never log these field values (security sensitive)
EXCLUDE_FIELDS = [
    'password',
    'password_hash',
    'secret',
    'token',
    'api_key'
]

# Redaction value for excluded fields
REDACTED_VALUE = '[REDACTED]'

# ============================================================================
# AUDIT SETTINGS
# ============================================================================

# Enable/disable audit logging globally
AUDIT_ENABLED = True

# Log system-initiated actions (not just user actions)
LOG_SYSTEM_ACTIONS = True

# Include request details (IP, session, endpoint)
LOG_REQUEST_DETAILS = True

# Generate checksums for integrity verification
GENERATE_CHECKSUMS = True
