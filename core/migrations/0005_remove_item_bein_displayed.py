# Generated by Django 2.2 on 2020-05-29 20:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_item_bein_displayed'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='item',
            name='bein_displayed',
        ),
    ]
