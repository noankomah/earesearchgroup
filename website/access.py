from django.db.models import Q

def assigned_to(user, model):
    if user.is_superuser:
        return model.objects.all()
    if not user.is_authenticated:
        return model.objects.none()
    return model.objects.filter(Q(owner=user) | Q(editor_group__in=user.groups.all())).distinct()

def can_publish(user, model):
    return user.is_superuser or user.has_perm(f"website.publish_{model._meta.model_name}")
