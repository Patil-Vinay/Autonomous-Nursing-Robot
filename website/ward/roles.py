from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

NURSE = 'Nurse'
DOCTOR = 'Doctor'


def in_group(user, name):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=name).exists())


def is_nurse(user):
    return in_group(user, NURSE)


def is_doctor(user):
    return in_group(user, DOCTOR)


def is_staff_member(user):
    return is_nurse(user) or is_doctor(user)


def role_required(test):
    """Sends visitors to sign in, signed in users without the role get a 403."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not test(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


# pages for both roles, and pages only nurses may use
staff_required = role_required(is_staff_member)
nurse_required = role_required(is_nurse)
