# Generated by Django 2.2.12 on 2020-05-29 09:24

from django.db import migrations, models
import time


class Migration(migrations.Migration):
    dependencies = [
        ("secateur", "0009_auto_20200222_1947"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="token_bucket_max",
            field=models.FloatField(default=100000.0),
        ),
        migrations.AddField(
            model_name="user",
            name="token_bucket_rate",
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name="user",
            name="token_bucket_time",
            field=models.FloatField(default=time.time),
        ),
        migrations.AddField(
            model_name="user",
            name="token_bucket_value",
            field=models.FloatField(default=100000.0),
        ),
    ]
