from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from panel.models import Empresa
from preferencias.models import Sucursal, AsignacionSucursalUsuario
from panel.context_processors import empresa_actual

class UserBranchPermissionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Crear Empresa
        self.empresa = Empresa.objects.create(nombre="Test Empresa", subdominio="test")
        
        # Crear Sucursales
        self.sucursal1 = Sucursal.objects.create(nombre="Sucursal 1", calle="Calle 1", ciudad="Ciudad 1", cp="12345", empresa=self.empresa)
        self.sucursal2 = Sucursal.objects.create(nombre="Sucursal 2", calle="Calle 2", ciudad="Ciudad 2", cp="67890", empresa=self.empresa)
        self.sucursal3 = Sucursal.objects.create(nombre="Sucursal 3", calle="Calle 3", ciudad="Ciudad 3", cp="11223", empresa=self.empresa)

        # Crear Usuario Admin y Usuario Normal
        self.admin_user = User.objects.create_user(username="admin@test", password="password", is_staff=True)
        self.normal_user = User.objects.create_user(username="user1@test", password="password")

    def test_obtener_sucursales_usuario_json_permission_denied(self):
        # Un usuario normal no puede acceder al endpoint AJAX
        self.client.login(username="user1@test", password="password")
        response = self.client.get(reverse('obtener_sucursales_usuario_json', args=[self.normal_user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode(), {'success': False, 'error': 'Acceso denegado'})

    def test_obtener_sucursales_usuario_json_success(self):
        # Admin puede consultar las sucursales del usuario
        self.client.login(username="admin@test", password="password")
        response = self.client.get(reverse('obtener_sucursales_usuario_json', args=[self.normal_user.id]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['username'], self.normal_user.username)
        self.assertEqual(len(data['sucursales']), 3)
        for s in data['sucursales']:
            self.assertFalse(s['asignada'])
            self.assertFalse(s['es_predeterminada'])

    def test_guardar_sucursales_usuario_ajax(self):
        self.client.login(username="admin@test", password="password")
        
        # Asignar sucursal 1 y 2, haciendo sucursal 2 predeterminada
        post_data = {
            'sucursales': [self.sucursal1.id, self.sucursal2.id],
            'predeterminada': self.sucursal2.id
        }
        response = self.client.post(reverse('guardar_sucursales_usuario_ajax', args=[self.normal_user.id]), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # Verificar en base de datos
        asignaciones = AsignacionSucursalUsuario.objects.filter(usuario=self.normal_user)
        self.assertEqual(asignaciones.count(), 2)
        
        asig_s1 = asignaciones.get(sucursal=self.sucursal1)
        self.assertFalse(asig_s1.es_predeterminada)
        
        asig_s2 = asignaciones.get(sucursal=self.sucursal2)
        self.assertTrue(asig_s2.es_predeterminada)

    def test_context_processor_restrictions_and_session_init(self):
        # Crear Rol con permiso para ver dashboard e inicio
        from preferencias.models import Rol, PermisoRolAccion, AsignacionRolUsuario
        rol = Rol.objects.create(nombre="Test Rol", empresa=self.empresa)
        PermisoRolAccion.objects.create(rol=rol, area='inicio', submodulo='dashboard', accion='ver', permitido=True)
        AsignacionRolUsuario.objects.create(usuario=self.normal_user, rol=rol, empresa=self.empresa)

        # Crear asignación para normal_user: sucursal 2 es predeterminada, sucursal 3 también asignada
        AsignacionSucursalUsuario.objects.create(usuario=self.normal_user, sucursal=self.sucursal2, es_predeterminada=True)
        AsignacionSucursalUsuario.objects.create(usuario=self.normal_user, sucursal=self.sucursal3, es_predeterminada=False)

        # Login con normal_user
        self.client.login(username="user1@test", password="password")
        
        # Simular request a una vista que renderice plantilla
        response = self.client.get(reverse('dashboard_inicio'))
        self.assertEqual(self.client.session.get('sucursal_id'), self.sucursal2.id)

        # Invocar directamente el context processor
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.normal_user
        request.session = self.client.session
        
        ctx = empresa_actual(request)
        self.assertEqual(ctx['empresa'], self.empresa)
        self.assertEqual(ctx['sucursal_actual_id'], self.sucursal2.id)
        
        self.assertEqual(ctx['sucursales_list'].count(), 2)
        self.assertIn(self.sucursal2, ctx['sucursales_list'])
        self.assertIn(self.sucursal3, ctx['sucursales_list'])
        self.assertNotIn(self.sucursal1, ctx['sucursales_list'])

    def test_inicio_permission_denied_redirect_to_first_permitted_module(self):
        # Crear Rol y Asignación de Permiso pero SIN permiso de inicio/dashboard.
        # En su lugar, dar acceso a Recursos Humanos -> Empleados
        from preferencias.models import Rol, PermisoRolAccion, AsignacionRolUsuario
        rol = Rol.objects.create(nombre="Test Rol 2", empresa=self.empresa)
        PermisoRolAccion.objects.create(rol=rol, area='recursos_humanos', submodulo='empleados', accion='ver', permitido=True)
        
        # Asignar rol a normal_user
        AsignacionRolUsuario.objects.create(usuario=self.normal_user, rol=rol, empresa=self.empresa)

        # Login
        self.client.login(username="user1@test", password="password")

        # Intentar acceder al inicio. Debe redirigir al módulo de empleados (/recursos-humanos/empleados/)
        response = self.client.get(reverse('dashboard_inicio'))
        self.assertRedirects(response, '/recursos-humanos/empleados/')
