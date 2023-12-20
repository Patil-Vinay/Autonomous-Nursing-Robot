from ward.roles import is_doctor, is_nurse


def roles(request):
    return {'is_nurse': is_nurse(request.user), 'is_doctor': is_doctor(request.user)}
