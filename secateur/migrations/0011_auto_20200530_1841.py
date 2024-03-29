# Generated by Django 3.0.6 on 2020-05-30 06:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("secateur", "0010_auto_20200529_2124"),
    ]

    operations = [
        migrations.AddField(
            model_name="logmessage",
            name="account",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="secateur.Account",
            ),
        ),
        migrations.AddField(
            model_name="logmessage",
            name="action",
            field=models.IntegerField(
                choices=[
                    (1, "Get User"),
                    (2, "Create Block"),
                    (3, "Destroy Block"),
                    (4, "Create Mute"),
                    (5, "Destroy Mute"),
                    (6, "Get Followers"),
                    (7, "Get Friends"),
                    (8, "Get Blocks"),
                    (9, "Get Mutes"),
                    (10, "Mute Followers"),
                    (11, "Block Followers"),
                    (12, "Login"),
                    (13, "Logout"),
                    (14, "Disconnect"),
                ],
                editable=False,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="logmessage",
            name="until",
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
