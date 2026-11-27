from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_trainingresult"),
    ]

    operations = [
        migrations.AddField(
            model_name="practicesession",
            name="session_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=40),
        ),
    ]
