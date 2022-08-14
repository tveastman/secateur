# Generated by Django 4.0.7 on 2022-08-14 01:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("secateur", "0047_alter_account_description_alter_account_location_and_more"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="relationship",
            name="until_btree",
        ),
        migrations.AddIndex(
            model_name="relationship",
            index=models.Index(
                condition=models.Q(("until__isnull", False)),
                fields=["until", "subject"],
                name="until_btree",
            ),
        ),
    ]