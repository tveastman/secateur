# Generated by Django 2.2.4 on 2019-08-28 06:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("secateur", "0006_auto_20190415_2116")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="secateur.Account",
            ),
        )
    ]
