# accounts/utils.py
def get_user_type(user):
    """
    Returns the type of user: 'student', 'digievolve_admin', 'django_admin', or None
    """
    from .models import StudentProfile, DigiEvolveAdmin

    if hasattr(user, 'studentprofile'):
        return 'student'
    elif hasattr(user, 'digievolveadmin'):
        return 'digievolve_admin'
    elif user.is_staff:
        return 'django_admin'
    return None