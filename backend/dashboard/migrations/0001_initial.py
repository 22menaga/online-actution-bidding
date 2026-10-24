from django.db import migrations,models
class Migration(migrations.Migration):
 initial=True
 operations=[migrations.CreateModel(name='SystemSetting',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('key',models.CharField(max_length=120,unique=True)),('value',models.TextField(blank=True)),('description',models.TextField(blank=True)),('updated_at',models.DateTimeField(auto_now=True))])]
