# Generated by Django 2.2 on 2019-04-15 09:16

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("secateur", "0005_user_is_twitter_api_enabled")]

    operations = [
        migrations.AlterField(
            model_name="account",
            name="profile",
            field=models.OneToOneField(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="secateur.Profile",
            ),
        )
    ]
