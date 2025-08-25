from flask_login import current_user
from functools import wraps
from flask import abort
from models import Role, RolePermission, Permission, db

def permission_required(*permission_keys):
    """
    Require at least one of permission_keys for any role the current_user has.
    Works with User.roles (many-to-many) or legacy current_user.role_id if present.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)

            # collect role ids from relationship or single role_id
            role_ids = set()
            user_roles = getattr(current_user, 'roles', None)
            if user_roles:
                for r in user_roles:
                    if getattr(r, 'id', None) is not None:
                        role_ids.add(r.id)

            single_role_id = getattr(current_user, 'role_id', None)
            if single_role_id is not None:
                role_ids.add(single_role_id)

            if not role_ids:
                abort(403)

            # ensure there is a row in role_permissions linking role_id <-> permission.key
            allowed = db.session.query(RolePermission).join(
                Permission, RolePermission.permission_id == Permission.id
            ).filter(
                RolePermission.role_id.in_(list(role_ids)),
                Permission.key.in_(permission_keys)
            ).first()

            if not allowed:
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator