# Generated by Django 3.0.7 on 2020-06-11 04:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("secateur", "0019_auto_20200611_1623"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="relationship",
            name="secateur_re_type_2c4b68_idx",
        ),
    ]
