from django.db import migrations,models
import django.db.models.deletion
class Migration(migrations.Migration):
 dependencies=[('accounts','0001_initial')]
 operations=[migrations.CreateModel(name='Notification',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('title',models.CharField(max_length=200)),('body',models.TextField()),('read_at',models.DateTimeField(blank=True,null=True)),('created_at',models.DateTimeField(auto_now_add=True)),('metadata',models.JSONField(blank=True,default=dict)),('recipient',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='notifications',to='accounts.user'))],options={'indexes':[models.Index(fields=['recipient','read_at','-created_at'],name='notificatio_recipien_44b8fd_idx')]})]
