# coding: utf-8

from __future__ import unicode_literals, print_function
from django.conf import settings
from django.contrib.contenttypes.generic import (
    GenericForeignKey, GenericRelation)
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import (
    Model, ForeignKey, PositiveIntegerField, TextField, FloatField,
    CharField, Q)
from django.db.models.query import QuerySet
from django.utils import translation
from django.utils.encoding import python_2_unicode_compatible
from django.utils.html import strip_tags
from model_utils.managers import PassThroughManager
from tqdm import tqdm
from django.utils.six import string_types
from .fields import VectorField

from .registry import search_registry
from .settings import *
from .utils import get_model_repr


search_registry.autodiscover()


SQL_INSERT = """
INSERT INTO %(table)s
    (language, content_type_id, object_id, url, thumbnail_url, boost,
     title, body,
     title_search, body_search)
SELECT
    language, content_type_id, object_id, url, thumbnail_url, boost,
    title, body,
    to_tsvector('%(dict)s', title),
    setweight(to_tsvector('%(dict)s', title), 'A')
    || setweight(to_tsvector('%(dict)s', body), 'C')
FROM (VALUES
    (%%s, %%s, %%s, %%s, %%s, %%s, %%s, %%s)
) AS data (language, content_type_id, object_id, url, thumbnail_url, boost,
           title, body)
"""


SQL_UPDATE = """
UPDATE %(table)s SET
    url = data.url,
    thumbnail_url = data.thumbnail_url,
    boost = data.boost,
    title = data.title,
    body = data.body,
    title_search = to_tsvector('%(dict)s', data.title),
    body_search = setweight(to_tsvector('%(dict)s', data.title), 'A')
    || setweight(to_tsvector('%(dict)s', data.body), 'C')
FROM (VALUES
    (%%s, %%s, %%s, %%s, %%s, %%s, %%s, %%s)
) AS data (language, content_type_id, object_id, url, thumbnail_url, boost,
           title, body)
WHERE (%(table)s.language = data.language
       AND %(table)s.content_type_id = data.content_type_id
       AND %(table)s.object_id = data.object_id)
"""


def get_params(obj):
    search_meta = search_registry[obj.__class__]
    title = search_meta.get_title(obj)
    if len(title) > TITLE_MAX_LENGTH:
        title = title[:TITLE_MAX_LENGTH-1] + '…'
    return (
        translation.get_language(),
        search_meta.get_absolute_url(obj),
        search_meta.get_thumbnail_url(obj),
        search_meta.get_boost(obj),
        title,
        strip_tags(search_meta.get_body(obj)),
    )


def rebuild_or_update(qs, sql, batch_size):
    qs = prefetch(qs).order_by()
    model = qs.model
    ct = ContentType.objects.get_for_model(model)
    cursor = connection.cursor()

    total = qs.count()
    data = []
    for i, obj in tqdm(enumerate(qs.iterator(), start=1),
                       total=total, leave=True):
        language, url, thumbnail_url, boost, title, body = get_params(obj)
        data.append((language, ct.pk, obj.pk, url, thumbnail_url, boost,
                     title, body))
        if i % batch_size == 0 or i == total:
            cursor.executemany(
                sql % {'table': Index._meta.db_table, 'dict': DICTIONARY},
                data)
            data = []
    cursor.close()
    print()  # Adds a new line because tqdm isn’t doing it


def get_sql(qs):
    return qs.query.get_compiler('default').as_sql()


def prefetch(qs):
    search_meta = search_registry[qs.model]
    sr_lookups = search_meta.select_relateds
    pr_lookups = search_meta.prefetch_relateds
    if sr_lookups:
        qs = qs.select_related(*sr_lookups)
    if pr_lookups:
        qs = qs.prefetch_related(*pr_lookups)
    return qs


def to_postgre_value(value):
    if isinstance(value, dict):
        return ', '.join(['%s=%s' % (k, to_postgre_value(v))
                          for k, v in value.items()])
    if isinstance(value, string_types):
        return "''%s''" % value
    return repr(value)


def postgresql_escape(sql, params):
    params = list(params)
    for i, param in enumerate(params):
        params[i] = param.replace('%', '%%')
    with connection.cursor() as cursor:
        return cursor.mogrify(sql, params).decode('utf-8')


class SafeFromClause(unicode):
    def startswith(self, prefix, start=None, end=None):
        if prefix == '"':
            return True
        return super(SafeFromClause, self).startswith(prefix,
                                                      start=start, end=end)


class IndexQuerySet(QuerySet):
    def for_language(self, lang_code=None):
        if lang_code is None:
            lang_code = translation.get_language()
        return self.filter(language=lang_code)

    def for_content_types(self, *content_types):
        return self.filter(content_type__in=content_types)

    def for_models(self, *models):
        cts = ContentType.objects.get_for_models(*models).values()
        return self.for_content_types(*cts)

    def for_querysets(self, *querysets):
        filters = Q()
        for qs in querysets:
            ct = ContentType.objects.get_for_model(qs.model)
            if qs.query.is_empty():
                continue
            if qs.query.where.children:
                filters |= (Q(content_type=ct)
                            & Q(object_id__in=qs.order_by().values('pk')))
            else:
                filters |= Q(content_type=ct)
        return self.filter(filters)

    def _inject_from(self, sql, params, alias):
        full_sql = postgresql_escape('%s AS "%s"' % (sql, alias), params)
        return self.extra(tables=[SafeFromClause(full_sql)],
                          select={alias: alias})

    def _sort(self, ts_vector):
        return self.extra(
            select={'rank': 'ts_rank(%s, query) * boost' % ts_vector},
        ).order_by('-rank')

    def defer_internals(self, defer_body=True):
        deferred = ['language', 'boost', 'title_search', 'body_search']
        if defer_body:
            deferred.append('body')
        return self.defer(*deferred)

    def search(self, term, sort=False, vector='body_search'):
        query = "plainto_tsquery('%s', %%s)" % DICTIONARY
        qs = self.for_language()._inject_from(query, [term], 'query')
        qs = qs.extra(where=['query @@ %s' % vector])
        if sort:
            qs = qs._sort(vector)
        return qs.defer_internals()

    def autocomplete(self, term, sort=False, vector='title_search'):
        query = "to_tsquery('%s', ''%%s':*')" % DICTIONARY
        term = term.replace("'", "''")
        qs = self.for_language()._inject_from(query, [term], 'query')
        qs = qs.extra(where=['query @@ %s' % vector])
        if sort:
            qs = qs._sort(vector)
        return qs.defer_internals()

    def highlight(self, **options):
        for k in options:
            if k not in HIGHLIGHT_DEFAULT_OPTIONS:
                raise KeyError('`%s` is not a valid highlighting option' % k)

        all_options = HIGHLIGHT_DEFAULT_OPTIONS.copy()
        all_options.update(options)

        sql, params = get_sql(
            self.defer(None).defer_internals(defer_body=False))
        if not sql:
            return self

        options_str = to_postgre_value(all_options)
        return Index.objects.raw(
            """
            SELECT id, content_type_id, object_id, url, thumbnail_url, title,
                   ts_headline('%s', t.body, t.query, '%s') AS highlight
            FROM (%s) AS t""" % (DICTIONARY, options_str, sql),
            params)


class IndexManager(PassThroughManager):
    queryset_class = IndexQuerySet

    def get_queryset(self):
        return self.queryset_class(self.model, using=self._db)

    def create_unindexed(self, model, batch_size):
        qs = search_registry[model].get_queryset().exclude(
            index_set__language=translation.get_language(),
            index_set__isnull=False)
        if not qs.exists():
            return

        print('Creating new entries...')
        rebuild_or_update(qs, SQL_INSERT, batch_size)

    def update_entries(self, model, batch_size):
        qs = search_registry[model].get_queryset().filter(
            index_set__language=translation.get_language())
        if not qs.exists():
            return

        print('Updating old entries...')
        rebuild_or_update(qs, SQL_UPDATE, batch_size)

    def delete_stale_entries(self, model):
        index_qs = (self.for_language().for_models(model)
                    .order_by().values('object_id'))
        qs = search_registry[model].get_queryset().order_by().values('pk')
        index_sql, index_params = get_sql(index_qs)
        qs_sql, qs_params = get_sql(qs)
        ids_sql = '(%s) EXCEPT (%s)' % (index_sql, qs_sql)
        params = index_params + qs_params

        cursor = connection.cursor()
        cursor.execute('SELECT EXISTS (%s);' % ids_sql, params)
        has_stale_entries = cursor.fetchone()[0]
        cursor.close()
        if not has_stale_entries:
            return

        print('Deleting stale entries...')
        cursor = connection.cursor()
        cursor.execute('DELETE FROM %s WHERE object_id IN (%s);'
                       % (Index._meta.db_table, ids_sql), params)
        cursor.close()

    def update_index(self, models=None, languages=None, rebuild=False,
                     batch_size=5000):
        if rebuild:
            print('Deleting indexes...')
            self.get_queryset().delete()

        if models is None:
            models = search_registry

        if languages is None:
            languages = [t[0] for t in settings.LANGUAGES]

        for lang_code in languages:
            translation.activate(lang_code)
            print("Indexing '%s' language..." % lang_code)
            for model in models:
                model_repr = get_model_repr(model)
                print('Indexing %s...' % model_repr)
                self.delete_stale_entries(model)
                self.update_entries(model, batch_size)
                self.create_unindexed(model, batch_size)

    def contribute_to_class(self, model, name):
        for registered in search_registry:
            GenericRelation(model).contribute_to_class(registered, 'index_set')
        super(IndexManager, self).contribute_to_class(model, name)


@python_2_unicode_compatible
class Index(Model):
    language = CharField(max_length=5, db_index=True)
    content_type = ForeignKey(ContentType)
    object_id = PositiveIntegerField()
    content_object = GenericForeignKey()
    url = CharField(max_length=300)
    thumbnail_url = CharField(max_length=300, blank=True)

    boost = FloatField(default=1.0)

    title = CharField(max_length=TITLE_MAX_LENGTH)
    body = TextField(blank=True)

    title_search = VectorField()
    body_search = VectorField()

    objects = IndexManager()

    class Meta(object):
        unique_together = (('language', 'content_type', 'object_id'),)

    def __str__(self):
        return '%s: %s' % (self.content_type.name, self.title)

    def get_absolute_url(self):
        return self.url
