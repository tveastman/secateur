# Generated by Django 3.0.7 on 2020-06-25 23:22

from django.db import migrations, models
import secateur.models


class Migration(migrations.Migration):
    dependencies = [
        ("secateur", "0024_remove_logmessage_message"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="token_bucket_max",
            field=models.FloatField(default=secateur.models.default_token_bucket_max),
        ),
        migrations.AlterField(
            model_name="user",
            name="token_bucket_rate",
            field=models.FloatField(default=secateur.models.default_token_bucket_rate),
        ),
        migrations.AlterField(
            model_name="user",
            name="token_bucket_value",
            field=models.FloatField(default=secateur.models.default_token_bucket_value),
        ),
    ]
