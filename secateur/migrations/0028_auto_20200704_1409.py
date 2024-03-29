# Generated by Django 3.0.7 on 2020-07-04 02:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("secateur", "0027_auto_20200704_1404"),
    ]

    operations = [
        migrations.AlterField(
            model_name="logmessage",
            name="user",
            field=models.ForeignKey(
                db_index=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="logmessage",
            index=models.Index(
                fields=["user", "action", "-time"],
                name="secateur_lo_user_id_d17035_idx",
            ),
        ),
    ]
