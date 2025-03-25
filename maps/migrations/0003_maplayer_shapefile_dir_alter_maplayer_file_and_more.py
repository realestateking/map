# Generated by Django 5.1.7 on 2025-03-24 19:42

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0002_maplayer'),
    ]

    operations = [
        migrations.AddField(
            model_name='maplayer',
            name='shapefile_dir',
            field=models.CharField(blank=True, help_text='Directory containing extracted shapefile components', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='maplayer',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='map_layers/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['json', 'geojson', 'kml', 'kmz', 'zip', 'shp'])]),
        ),
        migrations.AlterField(
            model_name='maplayer',
            name='layer_type',
            field=models.CharField(choices=[('geojson', 'GeoJSON'), ('kml', 'KML'), ('shapefile', 'Shapefile'), ('wms', 'WMS Service'), ('tile', 'Tile Layer')], max_length=10),
        ),
    ]
