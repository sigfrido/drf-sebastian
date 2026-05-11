from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('selco', '0002_fornitore_add_certificazione'),
    ]

    operations = [
        migrations.AddField(
            model_name='richiesta',
            name='motivazione',
            field=models.TextField(blank=True),
        ),
    ]
