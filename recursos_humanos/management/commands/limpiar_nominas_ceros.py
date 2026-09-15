from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from recursos_humanos.models import Nomina

class Command(BaseCommand):
    help = 'Elimina registros de nóminas cuyas percepciones sumen .00 o estén vacías.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra cuántos registros se eliminarían sin realizar cambios en la base de datos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write(self.style.NOTICE('Analizando nóminas en la base de datos...'))
        
        nominas = list(Nomina.objects.all())
        ceros_ids = [n.id for n in nominas if n.total_percepciones <= Decimal('0.00')]
        
        total_encontrados = len(ceros_ids)
        self.stdout.write(f'Se encontraron {total_encontrados} nóminas con percepciones en .00 de un total de {len(nominas)}.')
        
        if total_encontrados == 0:
            self.stdout.write(self.style.SUCCESS('No hay nóminas con .00 en percepciones. La base de datos está limpia.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Se habrían eliminado {total_encontrados} registros. No se realizaron cambios.'))
        else:
            with transaction.atomic():
                deleted_count, _ = Nomina.objects.filter(id__in=ceros_ids).delete()
                self.stdout.write(self.style.SUCCESS(f'Se eliminaron exitosamente {deleted_count} registros de nómina.'))
            self.stdout.write(f'Nóminas restantes en la base de datos: {Nomina.objects.count()}')
