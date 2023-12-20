from django.db import migrations


def add_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ('Nurse', 'Doctor'):
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('ward', '0001_initial'),
    ]

    operations = [migrations.RunPython(add_groups, migrations.RunPython.noop)]
