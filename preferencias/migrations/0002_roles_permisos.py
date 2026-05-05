from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0001_initial'),
        ('preferencias', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Rol',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=80, verbose_name='Nombre del Rol')),
                ('descripcion', models.CharField(blank=True, max_length=255, null=True, verbose_name='Descripción')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='panel.empresa', verbose_name='Empresa')),
            ],
            options={
                'verbose_name': 'Rol',
                'verbose_name_plural': 'Roles',
                'ordering': ['nombre'],
                'unique_together': {('empresa', 'nombre')},
            },
        ),
        migrations.CreateModel(
            name='PermisoRolModulo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modulo', models.CharField(choices=[('ventas', 'Ventas')], default='ventas', max_length=40)),
                ('puede_ver', models.BooleanField(default=False)),
                ('puede_crear', models.BooleanField(default=False)),
                ('puede_editar', models.BooleanField(default=False)),
                ('puede_eliminar', models.BooleanField(default=False)),
                ('puede_aprobar', models.BooleanField(default=False)),
                ('puede_imprimir', models.BooleanField(default=False)),
                ('rol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permisos_modulo', to='preferencias.rol')),
            ],
            options={
                'verbose_name': 'Permiso de Rol por Módulo',
                'verbose_name_plural': 'Permisos de Rol por Módulo',
                'unique_together': {('rol', 'modulo')},
            },
        ),
        migrations.CreateModel(
            name='AsignacionRolUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones_roles', to='panel.empresa')),
                ('rol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usuarios_asignados', to='preferencias.rol')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roles_empresa', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Asignación de Rol a Usuario',
                'verbose_name_plural': 'Asignaciones de Rol a Usuario',
                'unique_together': {('usuario', 'empresa')},
            },
        ),
    ]
