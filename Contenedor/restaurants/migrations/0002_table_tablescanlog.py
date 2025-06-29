# Generated by Django 5.2.2 on 2025-06-08 10:53

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        ('restaurants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Table',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=10, verbose_name='Número de mesa')),
                ('name', models.CharField(blank=True, max_length=100, verbose_name='Nombre descriptivo')),
                ('capacity', models.PositiveIntegerField(default=4, verbose_name='Capacidad (personas)')),
                ('qr_code_uuid', models.UUIDField(default=uuid.uuid4, unique=True, verbose_name='UUID para QR')),
                ('qr_enabled', models.BooleanField(default=True, verbose_name='QR habilitado')),
                ('location', models.CharField(blank=True, max_length=100, verbose_name='Ubicación (ej: terraza, interior)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Mesa activa')),
                ('total_scans', models.PositiveIntegerField(default=0, verbose_name='Total de escaneos')),
                ('last_scan', models.DateTimeField(blank=True, null=True, verbose_name='Último escaneo')),
                ('total_orders', models.PositiveIntegerField(default=0, verbose_name='Total de pedidos')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('restaurant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tables', to='restaurants.restaurant')),
            ],
            options={
                'verbose_name': 'Mesa',
                'verbose_name_plural': 'Mesas',
                'ordering': ['number'],
                'unique_together': {('restaurant', 'number')},
            },
        ),
        migrations.CreateModel(
            name='TableScanLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scanned_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('resulted_in_order', models.BooleanField(default=False, verbose_name='Resultó en pedido')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='orders.order')),
                ('table', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_logs', to='restaurants.table')),
            ],
            options={
                'verbose_name': 'Registro de escaneo QR',
                'verbose_name_plural': 'Registros de escaneos QR',
                'ordering': ['-scanned_at'],
            },
        ),
    ]
