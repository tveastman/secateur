# Generated by Django 3.1 on 2020-09-02 22:15

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("secateur", "0033_auto_20200830_1732"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="relationship",
            name="secateur_re_type_e76852_brin",
        ),
    ]
