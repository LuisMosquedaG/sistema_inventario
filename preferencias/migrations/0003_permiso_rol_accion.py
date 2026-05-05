from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('preferencias', '0002_roles_permisos'),
    ]

    operations = [
        migrations.CreateModel(
            name='PermisoRolAccion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area', models.CharField(choices=[('ventas', 'Ventas')], default='ventas', max_length=40)),
                ('submodulo', models.CharField(max_length=60)),
                ('accion', models.CharField(max_length=60)),
                ('permitido', models.BooleanField(default=False)),
                ('rol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permisos_accion', to='preferencias.rol')),
            ],
            options={
                'verbose_name': 'Permiso de Rol por Acción',
                'verbose_name_plural': 'Permisos de Rol por Acción',
                'unique_together': {('rol', 'area', 'submodulo', 'accion')},
            },
        ),
    ]
