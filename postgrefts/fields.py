# coding: utf-8

from __future__ import unicode_literals

import django
from django.db.models import Field, Aggregate
from django.db.models.sql.aggregates import Aggregate as SQLAggregate

from .settings import DICTIONARY


class VectorField(Field):
    def __init__(self, *args, **kwargs):
        kwargs.update(default='',
                      editable=False,
                      serialize=False,
                      db_index=False)
        super(VectorField, self).__init__(*args, **kwargs)

    def db_type(self, *args, **kwargs):
        return 'tsvector'


if django.VERSION >= (1, 7):
    from django.db.models import Lookup, Transform

    @VectorField.register_lookup
    class Search(Lookup):
        lookup_name = 'search'

        def as_sql(self, qn, connection):
            lhs, lhs_params = self.process_lhs(qn, connection)
            rhs, rhs_params = self.process_rhs(qn, connection)
            params = lhs_params + rhs_params
            return ("plainto_tsquery('%s', %s) "
                    "@@ %s" % (DICTIONARY, rhs, lhs),
                    params)


    @VectorField.register_lookup
    class Autocomplete(Lookup):
        lookup_name = 'autocomplete'

        def as_sql(self, qn, connection):
            lhs, lhs_params = self.process_lhs(qn, connection)
            rhs, rhs_params = self.process_rhs(qn, connection)
            assert len(rhs_params) == 1
            q = rhs_params[0]
            if not q:
                q = ' '
            else:
                q = q.replace("'", "''")
            return ("to_tsquery('%s', ''%s':*') "
                    "@@ %s" % (DICTIONARY, rhs, lhs),
                    [q])


    class Rank(Transform):
        lookup_name = 'rank'


    class SQLRank(SQLAggregate):
        is_ordinal = False
        is_computed = True
        sql_function = 'ts_rank'
        sql_template = ("""
        %(function)s(
            %(field)s,
            plainto_tsquery('%(dictionary)s', '%(q)s')
        )""")

        def __init__(self, col, source=None, is_summary=False, q='',
                     dictionary=DICTIONARY):
            super(SQLRank, self).__init__(
                col, source=source, is_summary=is_summary,
                q=q, dictionary=dictionary)


    class Rank(Aggregate):
        name = 'Rank'

        def add_to_query(self, query, alias, col, source, is_summary):
            query.aggregates[alias] = SQLRank(
                col, source=source, is_summary=is_summary, **self.extra)
