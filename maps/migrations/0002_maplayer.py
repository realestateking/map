# Generated by Django 5.1.7 on 2025-03-24 19:30

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MapLayer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('layer_type', models.CharField(choices=[('geojson', 'GeoJSON'), ('kml', 'KML'), ('wms', 'WMS Service'), ('tile', 'Tile Layer')], max_length=10)),
                ('url', models.URLField(blank=True, help_text='URL for WMS or Tile layers', null=True)),
                ('file', models.FileField(blank=True, null=True, upload_to='map_layers/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['json', 'geojson', 'kml', 'kmz'])])),
                ('style', models.JSONField(blank=True, help_text='JSON object with style options', null=True)),
                ('z_index', models.IntegerField(default=0, help_text='Order in layer control (higher values on top)')),
                ('is_active', models.BooleanField(default=True)),
                ('is_visible_by_default', models.BooleanField(default=False)),
                ('is_base_layer', models.BooleanField(default=False, help_text='If true, treated as a base map')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('region', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='layers', to='maps.region')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='map_layers', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-z_index', 'name'],
            },
        ),
    ]
