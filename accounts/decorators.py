from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def admin_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in first.")
            return redirect('accounts:admin_login')

        # Check if the user has admin privileges
        # User is an admin if user_type is 'admin' or 'both' AND admin_type is not 'none'
        is_admin_user = (request.user.user_type in ['admin', 'both'] and
                         request.user.admin_type != 'none')

        if not is_admin_user:
            messages.error(request, "You don't have DigiEvolve admin privileges.")
            return redirect('accounts:admin_login')

        # Check if the admin account is active
        if not request.user.is_active_admin:
            messages.error(request, "Your DigiEvolve admin account is inactive.")
            return redirect('accounts:admin_login')

        # Check if the user account is active (Django's built-in field)
        if not request.user.is_active:
            messages.error(request, "Your account is inactive.")
            return redirect('accounts:admin_login')

        return view_func(request, *args, **kwargs)
    return wrapper