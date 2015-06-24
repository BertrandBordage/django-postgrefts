# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import postgrefts.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Index',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('language', models.CharField(max_length=5, db_index=True)),
                ('object_id', models.PositiveIntegerField()),
                ('url', models.CharField(max_length=300)),
                ('thumbnail_url', models.CharField(max_length=300, blank=True)),
                ('boost', models.FloatField(default=1.0)),
                ('title', models.CharField(max_length=100)),
                ('body', models.TextField(blank=True)),
                ('title_search', postgrefts.fields.VectorField(default='', serialize=False, editable=False)),
                ('body_search', postgrefts.fields.VectorField(default='', serialize=False, editable=False)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='index',
            unique_together=set([('language', 'content_type', 'object_id')]),
        ),
        migrations.RunSQL("""
            CREATE EXTENSION IF NOT EXISTS unaccent;
            CREATE EXTENSION IF NOT EXISTS btree_gin;

            CREATE TEXT SEARCH CONFIGURATION fr ( COPY = french );
            CREATE TEXT SEARCH DICTIONARY fr_stop (
               TEMPLATE = simple,
               StopWords = 'french', Accept = false
            );
            -- myspell-fr must be installed in order to get this dict working.
            CREATE TEXT SEARCH DICTIONARY fr_ispell (
               TEMPLATE = ispell,
               DictFile = 'fr', AffFile = 'fr'
            );
            CREATE TEXT SEARCH DICTIONARY fr_stem (
               TEMPLATE = snowball,
               Language = 'french'
            );
            ALTER TEXT SEARCH CONFIGURATION fr
                ALTER MAPPING FOR asciihword, asciiword WITH fr_stop, fr_ispell, simple;
            ALTER TEXT SEARCH CONFIGURATION fr
                ALTER MAPPING FOR hword, hword_asciipart, hword_part, word WITH fr_stop, fr_ispell, unaccent, simple;

            CREATE INDEX content_type_id_title_search ON postgrefts_index USING gin(content_type_id, title_search);
            CREATE INDEX title_search ON postgrefts_index USING gin(title_search);
            CREATE INDEX body_search ON postgrefts_index USING gin(body_search);
            """),
    ]
