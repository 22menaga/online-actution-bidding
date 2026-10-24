from django.db import migrations


DEFAULT_CATEGORIES = (
    ("Electronics & Technology", "electronics-technology"),
    ("Fashion & Accessories", "fashion-accessories"),
    ("Home & Garden", "home-garden"),
    ("Sports & Outdoors", "sports-outdoors"),
    ("Toys & Games", "toys-games"),
    ("Automotive", "automotive"),
)


def add_default_categories(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    database = schema_editor.connection.alias
    manager = Category.objects.using(database)

    for name, slug in DEFAULT_CATEGORIES:
        if not manager.filter(slug=slug).exists() and not manager.filter(name=name).exists():
            manager.create(name=name, slug=slug, active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0002_rename_products_pro_status_c9d9d7_idx_products_pr_status_142af0_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(add_default_categories, migrations.RunPython.noop),
    ]
