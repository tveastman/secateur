# Generated by Django 4.0.4 on 2022-04-22 00:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("secateur", "0043_remove_logmessage_secateur_lo_user_id_a8697e_idx_and_more"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="logmessage",
            name="log_user_id_action",
        ),
        migrations.AddIndex(
            model_name="logmessage",
            index=models.Index(fields=["user", "-id"], name="log_user_id"),
        ),
    ]
