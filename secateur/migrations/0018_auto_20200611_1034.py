# Generated by Django 3.0.7 on 2020-06-10 22:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("secateur", "0017_auto_20200610_2103"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="account",
            index=models.Index(
                fields=["screen_name_lower"], name="secateur_ac_screen__cf1d38_idx"
            ),
        ),
    ]
