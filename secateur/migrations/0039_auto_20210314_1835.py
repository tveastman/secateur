# Generated by Django 3.1.6 on 2021-03-14 05:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("secateur", "0038_user_screen_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="token_bucket_time",
            field=models.FloatField(default=1),
        ),
    ]